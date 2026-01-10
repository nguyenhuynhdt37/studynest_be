# app/api/v1/user/chat_sql.py
"""
API endpoint cho Text-to-SQL chat.
Người dùng gửi câu hỏi tự nhiên, hệ thống trả về SQL SELECT query.

Tích hợp message_classifier để:
- NO_SEARCH: Xin chào, cảm ơn -> Trả lời ngay, không sinh SQL
- REUSE: Hỏi lại câu trước -> Dùng SQL cũ từ frontend
- SEARCH: Câu hỏi mới -> Sinh SQL mới
"""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.user.message_classifier import (
    MessageClassifierService,
    get_message_classifier_service,
)
from app.services.user.text_to_sql import TextToSqlService, get_text_to_sql_service

router = APIRouter(prefix="/chat-sql", tags=["Chat SQL"])


# =========================
# SCHEMAS
# =========================


class ChatSqlRequest(BaseModel):
    """Request body cho chat SQL."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="Câu hỏi tự nhiên"
    )
    previous_messages: Optional[List[str]] = Field(
        default=None, description="Lịch sử chat trước đó (tối đa 5 tin nhắn gần nhất)"
    )
    previous_sql: Optional[str] = Field(
        default=None, description="SQL của câu hỏi trước (để reuse nếu hỏi tiếp)"
    )


class ChatSqlResponse(BaseModel):
    """Response cho chat SQL."""

    success: bool
    mode: Literal["NO_SEARCH", "REUSE", "SEARCH"] = Field(description="Chế độ xử lý")
    sql: Optional[str] = None
    message: Optional[str] = None  # Tin nhắn phản hồi cho NO_SEARCH
    explanation: Optional[str] = None
    error: Optional[str] = None
    user_id: Optional[str] = None


class PreprocessResponse(BaseModel):
    """Response cho preprocessing."""

    original: str
    normalized: str
    language: str
    is_valid: bool
    error: Optional[str] = None


# =========================
# GREETING RESPONSES
# =========================

GREETING_RESPONSES = {
    "vi": "Xin chào! Tôi là trợ lý SQL. Bạn có thể hỏi tôi về dữ liệu khóa học, học viên, doanh thu... Ví dụ: 'Có bao nhiêu khóa học đang active?'",
    "en": "Hello! I'm the SQL assistant. You can ask me about courses, students, revenue... For example: 'How many active courses are there?'",
}

THANKS_RESPONSES = {
    "vi": "Không có gì! Nếu cần hỏi thêm về dữ liệu, cứ hỏi tôi nhé!",
    "en": "You're welcome! Feel free to ask me more about the data!",
}


# =========================
# ENDPOINTS
# =========================


@router.post("", response_model=ChatSqlResponse)
async def generate_sql_from_question(
    body: ChatSqlRequest,
    sql_service: TextToSqlService = Depends(get_text_to_sql_service),
    classifier: MessageClassifierService = Depends(get_message_classifier_service),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    """
    Chuyển đổi câu hỏi tự nhiên thành SQL SELECT.

    **Workflow:**
    1. Phân loại câu hỏi (NO_SEARCH / REUSE / SEARCH)
    2. NO_SEARCH: Trả lời xã giao ngay
    3. REUSE: Dùng lại SQL từ `previous_sql`
    4. SEARCH: Sinh SQL mới từ câu hỏi

    **Request:**
    - `question`: Câu hỏi bằng tiếng Việt hoặc tiếng Anh
    - `previous_messages`: Lịch sử chat (để classifier hiểu ngữ cảnh)
    - `previous_sql`: SQL của câu trước (để reuse)

    **Ví dụ:**
    - "Xin chào" → NO_SEARCH, trả lời chào
    - "Giải thích thêm đi" → REUSE, dùng SQL cũ
    - "Có bao nhiêu khóa học?" → SEARCH, sinh SQL mới
    """
    user: User = await auth.get_current_user()

    # Xác định có context trước không
    has_prev_context = bool(body.previous_sql)

    # Chuyển previous_messages thành list dict cho classifier
    chat_history = None
    if body.previous_messages:
        chat_history = [{"content": msg} for msg in body.previous_messages[-5:]]

    # Bước 1: Phân loại câu hỏi
    classify_result = await classifier.classify_message(
        message=body.question,
        chat_history=chat_history,
        has_prev_context=has_prev_context,
    )

    mode = classify_result["mode"]

    # Bước 2: Xử lý theo mode
    if mode == "NO_SEARCH":
        # Câu xã giao -> Trả lời ngay
        lang = sql_service.preprocess(body.question).language

        # Detect greeting vs thanks
        q_lower = body.question.lower()
        if any(w in q_lower for w in ["cảm ơn", "thank", "thanks", "cám ơn"]):
            message = THANKS_RESPONSES.get(lang, THANKS_RESPONSES["vi"])
        else:
            message = GREETING_RESPONSES.get(lang, GREETING_RESPONSES["vi"])

        return ChatSqlResponse(
            success=True,
            mode="NO_SEARCH",
            sql=None,
            message=message,
            user_id=str(user.id),
        )

    elif mode == "REUSE":
        # Hỏi tiếp câu trước -> Dùng SQL cũ
        if body.previous_sql:
            return ChatSqlResponse(
                success=True,
                mode="REUSE",
                sql=body.previous_sql,
                message="Sử dụng lại SQL từ câu hỏi trước.",
                explanation="Câu hỏi của bạn tham chiếu đến nội dung trước đó.",
                user_id=str(user.id),
            )
        else:
            # Không có SQL cũ -> Fallback sang SEARCH
            mode = "SEARCH"

    # Xác định role của user (đơn giản: check từ user object hoặc roles)
    # TODO: Lấy role thực từ user.roles nếu có
    user_role = "student"  # Default
    if hasattr(user, "roles") and user.roles:
        role_names = [
            r.role_name.lower() if hasattr(r, "role_name") else str(r).lower()
            for r in user.roles
        ]
        if "admin" in role_names:
            user_role = "admin"
        elif "lecturer" in role_names or "instructor" in role_names:
            user_role = "instructor"

    # mode == "SEARCH": Sinh SQL mới với authorization
    result = await sql_service.generate_sql(
        question=body.question, user_id=str(user.id), user_role=user_role
    )

    # Check if LLM denied the request
    if result.sql and result.sql.upper().startswith("DENIED"):
        return ChatSqlResponse(
            success=False,
            mode="SEARCH",
            sql=None,
            message=None,
            explanation=None,
            error=result.sql,  # "DENIED: lý do"
            user_id=str(user.id),
        )

    return ChatSqlResponse(
        success=result.success,
        mode="SEARCH",
        sql=result.sql,
        message=None,
        explanation=result.explanation,
        error=result.error,
        user_id=str(user.id),
    )


@router.post("/preprocess", response_model=PreprocessResponse)
async def preprocess_question(
    body: ChatSqlRequest,
    service: TextToSqlService = Depends(get_text_to_sql_service),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    """
    Tiền xử lý câu hỏi (debug/testing).

    Trả về kết quả preprocessing:
    - Chuẩn hóa unicode
    - Mở rộng viết tắt
    - Phát hiện ngôn ngữ
    """
    await auth.get_current_user()

    result = service.preprocess(body.question)

    return PreprocessResponse(
        original=result.original,
        normalized=result.normalized,
        language=result.language,
        is_valid=result.is_valid,
        error=result.error,
    )


@router.post("/validate")
async def validate_sql(
    sql: str,
    service: TextToSqlService = Depends(get_text_to_sql_service),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    """
    Kiểm tra SQL có an toàn không.

    Chỉ cho phép SELECT, chặn UPDATE/DELETE/DROP.
    """
    await auth.get_current_user()

    is_safe = service.validate_sql(sql)

    return {
        "sql": sql,
        "is_safe": is_safe,
        "message": (
            "SQL hợp lệ" if is_safe else "SQL không an toàn (chỉ cho phép SELECT)"
        ),
    }


@router.post("/classify")
async def classify_question(
    body: ChatSqlRequest,
    classifier: MessageClassifierService = Depends(get_message_classifier_service),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    """
    Debug endpoint: Chỉ phân loại câu hỏi mà không sinh SQL.

    Trả về: NO_SEARCH, REUSE, hoặc SEARCH
    """
    await auth.get_current_user()

    has_prev_context = bool(body.previous_sql)
    chat_history = None
    if body.previous_messages:
        chat_history = [{"content": msg} for msg in body.previous_messages[-5:]]

    result = await classifier.classify_message(
        message=body.question,
        chat_history=chat_history,
        has_prev_context=has_prev_context,
    )

    return result


# =========================
# FULL PIPELINE ENDPOINT
# =========================


class ChatCompleteRequest(BaseModel):
    """Request cho full pipeline."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="Câu hỏi tự nhiên"
    )
    history: Optional[List[str]] = Field(
        default=None, description="Lịch sử chat trước đó (tối đa 10 tin nhắn gần nhất)"
    )


class ChatCompleteResponse(BaseModel):
    """Response đơn giản - chỉ trả về message."""

    response: str = Field(description="Câu trả lời bằng ngôn ngữ tự nhiên")


@router.post("/complete", response_model=ChatCompleteResponse)
async def chat_complete(
    body: ChatCompleteRequest,
    service: TextToSqlService = Depends(get_text_to_sql_service),
    classifier: MessageClassifierService = Depends(get_message_classifier_service),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    """
    **Chat Bot**: Hỏi đáp về dữ liệu bằng ngôn ngữ tự nhiên.

    **Request:**
    - `question`: Câu hỏi hiện tại
    - `history`: Lịch sử chat trước đó (optional)

    **Ví dụ:**
    - "Có bao nhiêu khóa học của tôi?" → "Bạn hiện có 5 khóa học."
    - "Xin chào" → "Xin chào! Tôi có thể giúp gì cho bạn?"
    """
    user: User = await auth.get_current_user()

    # Chuẩn bị chat history cho classifier
    chat_history = None
    has_prev_context = False
    if body.history:
        chat_history = [{"content": msg} for msg in body.history[-10:]]
        has_prev_context = True

    # Check for greeting/thanks/follow-up
    classify_result = await classifier.classify_message(
        message=body.question,
        chat_history=chat_history,
        has_prev_context=has_prev_context,
    )

    mode = classify_result["mode"]

    if mode == "NO_SEARCH":
        # Greeting - respond without SQL
        lang = service.preprocess(body.question).language
        q_lower = body.question.lower()
        if any(w in q_lower for w in ["cảm ơn", "thank", "thanks", "cám ơn"]):
            message = THANKS_RESPONSES.get(lang, THANKS_RESPONSES["vi"])
        else:
            message = GREETING_RESPONSES.get(lang, GREETING_RESPONSES["vi"])

        return ChatCompleteResponse(response=message)

    # Determine user role
    user_role = "student"
    if hasattr(user, "roles") and user.roles:
        role_names = [
            r.role_name.lower() if hasattr(r, "role_name") else str(r).lower()
            for r in user.roles
        ]
        if "admin" in role_names:
            user_role = "admin"
        elif "lecturer" in role_names or "instructor" in role_names:
            user_role = "instructor"

    # Full pipeline (with history context for better SQL generation)
    result = await service.chat_complete(
        question=body.question,
        user_id=str(user.id),
        user_role=user_role,
        history=body.history,
    )

    return ChatCompleteResponse(
        response=result.natural_response or "Xin lỗi, tôi không thể xử lý câu hỏi này."
    )
