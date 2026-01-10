# app/services/user/text_to_sql.py
"""
TextToSqlService - Chuyển đổi câu hỏi tự nhiên thành SQL SELECT.

Mục tiêu:
- Nhận câu hỏi tiếng Việt/Anh của người dùng
- Tiền xử lý và chuẩn hóa
- Sinh câu lệnh SQL SELECT dựa trên database schema
- Thực thi SQL và format kết quả thành ngôn ngữ tự nhiên

Lưu ý bảo mật:
- Chỉ cho phép SELECT
- Không cho phép UPDATE/DELETE/DROP/INSERT/ALTER/TRUNCATE
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import Depends
from sqlalchemy import text

from app.core.llm import LLMService
from app.core.settings import settings
from app.db.sesson import AsyncSessionLocal

# =========================
# DATA CLASSES
# =========================


@dataclass
class PreprocessResult:
    """Kết quả tiền xử lý."""

    original: str
    normalized: str
    language: str  # "vi" | "en" | "mixed"
    is_valid: bool
    error: Optional[str] = None


@dataclass
class SqlGenerationResult:
    """Kết quả sinh SQL."""

    success: bool
    sql: Optional[str] = None
    explanation: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SqlExecutionResult:
    """Kết quả thực thi SQL."""

    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ChatSqlFullResult:
    """Kết quả đầy đủ: Question -> SQL -> Data -> Natural Language."""

    success: bool
    mode: str = "SEARCH"  # NO_SEARCH | REUSE | SEARCH
    sql: Optional[str] = None
    data: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    natural_response: Optional[str] = None  # Câu trả lời bằng ngôn ngữ tự nhiên
    error: Optional[str] = None


# =========================
# DATABASE SCHEMA (cho LLM context)
# =========================


# =========================
# DATABASE SCHEMA (Dynamic Load from Code)
# =========================
try:
    import inspect

    from app.db.models import database

    # Load source code of database models to give LLM full context of relationships & types
    DATABASE_SCHEMA = inspect.getsource(database)
except Exception as e:
    print(f"Error loading database schema code: {e}")
    DATABASE_SCHEMA = """
    Please refer to app/db/models/database.py for full schema.
    Key tables: user, courses, course_enrollments, lessons, lesson_progress, transactions.
    """


# =========================
# PREPROCESSING
# =========================


def normalize_unicode(text: str) -> str:
    """Chuẩn hóa unicode NFC."""
    return unicodedata.normalize("NFC", text)


def expand_abbreviations(text: str) -> str:
    """Mở rộng các từ viết tắt tiếng Việt phổ biến."""
    abbr_map = {
        r"\bkh\b": "khóa học",
        r"\bgv\b": "giảng viên",
        r"\bhv\b": "học viên",
        r"\bdn\b": "doanh nghiệp",
        r"\bdt\b": "doanh thu",
        r"\btk\b": "tài khoản",
        r"\bsl\b": "số lượng",
        r"\btb\b": "trung bình",
        r"\bng\b": "người",
    }
    result = text.lower()
    for pattern, replacement in abbr_map.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def detect_language(text: str) -> str:
    """Phát hiện ngôn ngữ đơn giản."""
    vn_chars = set(
        "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    )
    text_lower = text.lower()
    has_vn = any(c in vn_chars for c in text_lower)

    # Các từ tiếng Việt phổ biến
    vn_words = [
        "là",
        "của",
        "và",
        "có",
        "được",
        "cho",
        "trong",
        "không",
        "này",
        "những",
        "bao nhiêu",
        "mấy",
    ]
    has_vn_word = any(w in text_lower for w in vn_words)

    if has_vn or has_vn_word:
        return "vi"
    return "en"


def clean_whitespace(text: str) -> str:
    """Loại bỏ khoảng trắng thừa."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


# =========================
# VALIDATION
# =========================


FORBIDDEN_KEYWORDS = [
    "UPDATE",
    "DELETE",
    "DROP",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "--",
    "/*",
    "UNION",
    "INTO OUTFILE",
    "LOAD_FILE",
]


def is_safe_sql(sql: str) -> bool:
    """Kiểm tra SQL có an toàn không (chỉ SELECT)."""
    # Remove comments -- and /* */
    sql_clean = re.sub(r"--.*", "", sql)
    sql_clean = re.sub(r"/\*[\s\S]*?\*/", "", sql_clean)

    sql_upper = sql_clean.upper().strip()

    # Phải bắt đầu bằng SELECT hoặc WITH (CTE)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Không chứa các từ khóa nguy hiểm
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword == "--" or keyword == "/*":
            continue  # Skip comments check
        if keyword in sql_upper:
            return False

    return True


def extract_sql_from_response(response: str) -> Optional[str]:
    """Trích xuất SQL từ response của LLM."""

    # Helper to clean SQL
    def clean_sql(s):
        s = re.sub(r"--.*", "", s)
        s = re.sub(r"/\*[\s\S]*?\*/", "", s)
        return s.strip()

    # Thử tìm trong code block ```sql ... ```
    match = re.search(r"```sql\s*([\s\S]*?)\s*```", response, re.IGNORECASE)
    if match:
        return clean_sql(match.group(1))

    # Thử tìm trong code block ``` ... ```
    match = re.search(r"```\s*([\s\S]*?)\s*```", response)
    if match:
        candidate = clean_sql(match.group(1))
        if candidate.upper().startswith("SELECT") or candidate.upper().startswith(
            "WITH"
        ):
            return candidate

    # Tìm SELECT statement trực tiếp
    # Regex tìm từ khóa SELECT đến hết câu ; (hoặc hết string nếu không có ;)
    match = re.search(r"\bSELECT\b[\s\S]+?;", response, re.IGNORECASE)
    if match:
        return clean_sql(match.group(0))

    return None

    # Nếu response chỉ là SQL thuần
    if response.strip().upper().startswith("SELECT"):
        return response.strip()

    return None


# =========================
# SERVICE
# =========================


class TextToSqlService:
    """
    Service chuyển đổi câu hỏi tự nhiên thành SQL SELECT.

    Workflow:
    1. preprocess() - Tiền xử lý câu hỏi
    2. generate_sql() - Gọi LLM sinh SQL
    3. validate_sql() - Kiểm tra SQL an toàn
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def _get_full_url(self, path: str) -> str:
        """Convert local path to full URL."""
        if not path:
            return ""
        if path.startswith(("http:", "https:")):
            return path
        base = settings.BACKEND_URL or "http://localhost:8000"
        return f"{base.rstrip('/')}/{path.lstrip('/')}"

    def preprocess(self, question: str) -> PreprocessResult:
        """
        Tiền xử lý câu hỏi người dùng.

        Các bước:
        1. Chuẩn hóa unicode
        2. Loại bỏ khoảng trắng thừa
        3. Mở rộng viết tắt
        4. Phát hiện ngôn ngữ
        5. Validate input
        """
        if not question or not question.strip():
            return PreprocessResult(
                original=question or "",
                normalized="",
                language="unknown",
                is_valid=False,
                error="Câu hỏi không được để trống",
            )

        # Bước 1: Unicode NFC
        normalized = normalize_unicode(question)

        # Bước 2: Clean whitespace
        normalized = clean_whitespace(normalized)

        # Bước 3: Expand abbreviations
        normalized = expand_abbreviations(normalized)

        # Bước 4: Detect language
        language = detect_language(normalized)

        # Bước 5: Validate
        if len(normalized) < 3:
            return PreprocessResult(
                original=question,
                normalized=normalized,
                language=language,
                is_valid=False,
                error="Câu hỏi quá ngắn",
            )

        if len(normalized) > 500:
            return PreprocessResult(
                original=question,
                normalized=normalized[:500],
                language=language,
                is_valid=False,
                error="Câu hỏi quá dài (tối đa 500 ký tự)",
            )

        return PreprocessResult(
            original=question, normalized=normalized, language=language, is_valid=True
        )

    async def generate_sql(
        self,
        question: str,
        user_id: str = None,
        user_role: str = "student",  # "student" | "instructor" | "admin"
        history: List[str] = None,
    ) -> SqlGenerationResult:
        """
        Sinh SQL SELECT từ câu hỏi tự nhiên.

        Args:
            question: Câu hỏi của người dùng
            user_id: ID người dùng hiện tại (để restrict data)
            user_role: Role của user (student/instructor/admin)
            history: Lịch sử chat (để hiểu ngữ cảnh)

        Returns:
            SqlGenerationResult với SQL query hoặc error
        """
        # Tiền xử lý
        prep = self.preprocess(question)
        if not prep.is_valid:
            return SqlGenerationResult(success=False, error=prep.error)

        # Tạo prompt cho LLM với authorization context
        prompt = self._build_prompt(
            prep.normalized, prep.language, user_id, user_role, history
        )

        try:
            # Gọi LLM
            response = await self.llm_service.call_model(
                prompt=prompt,
                mime_type="text/plain",
                temperature=0.2,
                max_output_tokens=2000,
            )

            if not response:
                return SqlGenerationResult(
                    success=False, error="LLM không trả về kết quả"
                )

            # Debug: In response để xem LLM trả về gì
            print(f"[DEBUG] LLM Response:\n{response[:500]}...")

            # Trích xuất SQL
            sql = extract_sql_from_response(response)

            if not sql:
                # Nếu không extract được, thử lấy toàn bộ response nếu nó giống SQL
                if "SELECT" in response.upper():
                    # Tìm từ SELECT đến hết hoặc đến dấu chấm phẩy
                    match = re.search(
                        r"(SELECT[^;]+)", response, re.IGNORECASE | re.DOTALL
                    )
                    if match:
                        sql = match.group(1).strip()
                        # Thêm dấu ; nếu chưa có
                        if not sql.endswith(";"):
                            sql = sql + ";"

                if not sql:
                    return SqlGenerationResult(
                        success=False,
                        error=f"Không thể trích xuất SQL từ response. Response preview: {response[:200]}...",
                    )

            # Validate SQL
            if not is_safe_sql(sql):
                return SqlGenerationResult(
                    success=False,
                    error=f"SQL không an toàn. SQL: {sql[:100]}...",
                )

            return SqlGenerationResult(
                success=True, sql=sql, explanation=self._extract_explanation(response)
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return SqlGenerationResult(
                success=False, error=f"Lỗi khi sinh SQL: {str(e)}"
            )

    def validate_sql(self, sql: str) -> bool:
        """Kiểm tra SQL có hợp lệ và an toàn không."""
        return is_safe_sql(sql)

    def _build_prompt(
        self,
        question: str,
        language: str,
        user_id: str = None,
        user_role: str = "student",
        history: List[str] = None,
    ) -> str:
        """Xây dựng prompt cho LLM với authorization context."""
        lang_instruction = (
            "Trả lời bằng tiếng Việt." if language == "vi" else "Answer in English."
        )

        # Authorization rules based on role
        if user_role == "admin":
            auth_rules = """
## QUYỀN TRUY CẬP: ADMIN
- Bạn có thể truy cập TẤT CẢ dữ liệu trong hệ thống
- Không cần filter theo user_id
"""
        elif user_role == "instructor":
            auth_rules = f"""
## QUYỀN TRUY CẬP: GIẢNG VIÊN (instructor_id = '{user_id}')
- Chỉ được xem dữ liệu của CHÍNH MÌNH:
  + courses: WHERE instructor_id = '{user_id}'
  + instructor_earnings: WHERE instructor_id = '{user_id}'
  + course_enrollments: chỉ các khóa học của mình
  + course_reviews: chỉ các khóa học của mình
- KHÔNG được xem dữ liệu của giảng viên khác hoặc toàn bộ hệ thống
- Khi người dùng hỏi "doanh thu của tôi", "khóa học của tôi" -> filter theo instructor_id = '{user_id}'
"""
        else:  # student / guest
            auth_rules = f"""
## QUYỀN TRUY CẬP: HỌC VIÊN / NGƯỜI DÙNG CHUNG (user_id = '{user_id}')

1. **Dữ liệu Cá nhân** (Yêu cầu filter user_id = '{user_id}'):
   - Các khóa học ĐÃ ĐĂNG KÝ: `course_enrollments`
   - Tiến độ học: `lesson_progress`
   - Giao dịch cá nhân: `transactions`, `user_transaction`
   - Đánh giá của tôi: `course_reviews` (WHERE user_id = '{user_id}')
   - Ví dụ: "khóa học của tôi", "tôi đã học được bao nhiêu", "lịch sử mua hàng của tôi"

2. **Dữ liệu Công khai** (ĐƯỢC PHÉP xem toàn bộ):
   - Danh sách khóa học: `courses` (WHERE is_published = true)
   - Danh mục: `categories`, `topics`
   - Giảng viên công khai: `user` (thông tin cơ bản)
   - Đánh giá công khai của khóa học: `course_reviews` (của khóa học bất kỳ)
   - Thống kê chung: Đếm số lượng khóa học, học viên, đánh giá trung bình.
   - **QUAN TRỌNG**: Khi hỏi "bán chạy", "hot", "phổ biến", "đông học viên" -> dùng cột `total_enrolls` (KHÔNG dùng doanh thu).
   - Ví dụ: "khóa học bán chạy nhất" -> `ORDER BY total_enrolls DESC`

3. **Bị CẤM**:
   - Doanh thu của hệ thống hoặc giảng viên (trừ khi là chính mình).
   - Thông tin cá nhân nhạy cảm của người khác (email, sđt).
"""

        history_section = ""
        if history:
            history_str = "\n".join([f"- {msg}" for msg in history[-6:]])
            history_section = f"""
## LỊCH SỬ CHAT (context):
{history_str}
Lưu ý quan trọng: 
- Nếu câu hỏi ám chỉ đối tượng trước đó (vd: "nó", "khóa học đó"), hãy dùng context để xác định ID/Tên.
- Nếu câu hỏi là "**cho thêm thông tin**", "**chi tiết hơn**" -> Hãy tạo SQL `SELECT *` cho các entity (khóa học, user...) vừa được nhắc đến trong câu trả lời trước đó của Bot.
"""

        return f"""Bạn là chuyên gia SQL. Nhiệm vụ: chuyển câu hỏi tự nhiên thành SQL SELECT.

{DATABASE_SCHEMA}

{auth_rules}

{history_section}

RULES:
1. CHỈ trả về câu lệnh SELECT - KHÔNG được dùng UPDATE/DELETE/INSERT/DROP
2. Sử dụng đúng tên bảng và cột như trong schema
3. Thêm LIMIT nếu câu hỏi không chỉ rõ số lượng  
4. Dùng alias cho các cột để dễ đọc
5. Format SQL đẹp, dễ đọc
6. **Ưu tiên SELECT cột `thumbnail_url` (nếu có) để hiển thị ảnh.**
7. Với bảng user, schema đầy đủ là: public.user
8. BẮT BUỘC tuân thủ quyền truy cập ở trên - TỪ CHỐI nếu câu hỏi vượt quyền

Câu hỏi: {question}

{lang_instruction}

Nếu câu hỏi vượt quyền truy cập, trả về: "DENIED: [lý do]"
Nếu hợp lệ, trả về SQL trong block ```sql ... ``` và giải thích ngắn gọn.
"""

    def _extract_explanation(self, response: str) -> Optional[str]:
        """Trích xuất phần giải thích (nếu có)."""
        # Loại bỏ phần SQL block
        text = re.sub(r"```sql[\s\S]*?```", "", response, flags=re.IGNORECASE)
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = text.strip()

        if text:
            # Giới hạn độ dài
            return text[:300] if len(text) > 300 else text
        return None

    # =========================
    # SQL EXECUTION
    # =========================

    async def execute_sql(self, sql: str) -> SqlExecutionResult:
        """
        Thực thi SQL SELECT và trả về kết quả.

        Chỉ cho phép SELECT để đảm bảo an toàn.
        """
        if not is_safe_sql(sql):
            return SqlExecutionResult(
                success=False, error="Chỉ được phép thực thi SELECT statements."
            )

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text(sql))
                rows = result.fetchall()
                columns = list(result.keys()) if result.keys() else []

                # Convert rows to list of dicts
                data = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Handle special types (UUID, datetime, Decimal)
                        if hasattr(value, "isoformat"):
                            value = value.isoformat()
                        elif hasattr(value, "hex"):  # UUID
                            value = str(value)
                        elif hasattr(value, "__float__"):  # Decimal
                            value = float(value)

                        # Tự động convert URL ảnh nếu tên cột gợi ý
                        if isinstance(value, str) and any(
                            k in col.lower()
                            for k in [
                                "image",
                                "thumbnail",
                                "avatar",
                                "banner",
                                "picture",
                                "photo",
                            ]
                        ):
                            value = self._get_full_url(value)

                        row_dict[col] = value
                    data.append(row_dict)

                return SqlExecutionResult(
                    success=True, data=data, row_count=len(data), columns=columns
                )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return SqlExecutionResult(
                success=False, error=f"Lỗi thực thi SQL: {str(e)}"
            )

    # =========================
    # NATURAL LANGUAGE RESPONSE
    # =========================

    async def format_response(
        self,
        question: str,
        sql: str,
        data: List[Dict[str, Any]],
        row_count: int,
        language: str = "vi",
    ) -> str:
        """
        Dùng LLM để format kết quả thành ngôn ngữ tự nhiên.
        """
        # Giới hạn data để tránh prompt quá dài
        data_preview = data[:20] if len(data) > 20 else data

        prompt = f"""Bạn là StudyNest AI 🌟 - trợ lý ảo thông minh của vinhuni.
Nhiệm vụ: Trả lời câu hỏi của người dùng dựa trên dữ liệu tìm được một cách chuyên nghiệp, đẹp mắt và thân thiện.

Câu hỏi: {question}

Dữ liệu tìm được ({row_count} dòng):
```json
{json.dumps(data_preview, ensure_ascii=False, indent=2)}
```
{"(Dữ liệu mẫu 20 dòng đầu)" if len(data) > 20 else ""}

Yêu cầu định dạng (Markdown):
1. **Phong cách**: Thân thiện, nhiệt tình, sử dụng emoji tự nhiên (📚, 🚀, ❤️, ✅...).
2. **Trình bày**:
   - Mở đầu ấn tượng.
   - **Tóm tắt**: Câu trả lời trực tiếp vào vấn đề.
   - **HIỂN THỊ ẢNH**: Nếu có URL ảnh (thumbnail, banner...), bắt buộc hiển thị bằng cú pháp `![Alt](url)` ở đầu hoặc trong bảng.
   - **Chi tiết**: Sử dụng Bullet points hoặc **Bảng Markdown** nếu có nhiều dữ liệu so sánh.
   - Format tiền tệ (VD: 50,000 đ), ngày tháng rõ ràng.
3. **Ngôn ngữ**: {"Tiếng Việt" if language == "vi" else "English"}.

Lưu ý:
- Hãy làm cho câu trả lời trông thật "đẹp trai" và dễ đọc trên mobile/web.
- Không nhắc đến "SQL" hay "JSON" hay "database".
"""

        try:
            response = await self.llm_service.call_model(
                prompt=prompt,
                mime_type="text/plain",
                temperature=0.7,
                max_output_tokens=1000,
            )
            return response.strip() if response else "Đã thực hiện truy vấn thành công."
        except Exception:
            # Fallback: trả về kết quả đơn giản
            if row_count == 0:
                return "Không tìm thấy dữ liệu nào phù hợp với yêu cầu."
            elif row_count == 1:
                return f"Tìm thấy 1 kết quả: {json.dumps(data[0], ensure_ascii=False)}"
            else:
                return f"Tìm thấy {row_count} kết quả."

    # =========================
    # FULL PIPELINE: Question -> SQL -> Execute -> Response
    # =========================

    async def chat_complete(
        self,
        question: str,
        user_id: str = None,
        user_role: str = "student",
        history: List[str] = None,
    ) -> ChatSqlFullResult:
        """
        Pipeline đầy đủ:
        1. Sinh SQL từ câu hỏi
        2. Thực thi SQL
        3. Format kết quả thành ngôn ngữ tự nhiên

        Luôn trả về response thân thiện, kể cả khi lỗi.
        """
        prep = self.preprocess(question)

        # Bước 1: Sinh SQL
        sql_result = await self.generate_sql(question, user_id, user_role, history)

        if not sql_result.success:
            # Trả về message thân thiện thay vì error kỹ thuật
            friendly_msg = await self._generate_friendly_error(
                question, sql_result.error, prep.language
            )
            return ChatSqlFullResult(
                success=True,  # Vẫn success vì có response
                natural_response=friendly_msg,
            )

        # Check DENIED
        if sql_result.sql and sql_result.sql.upper().startswith("DENIED"):
            friendly_msg = await self._generate_friendly_error(
                question, sql_result.sql, prep.language
            )
            return ChatSqlFullResult(success=True, natural_response=friendly_msg)

        # Bước 2: Thực thi SQL
        exec_result = await self.execute_sql(sql_result.sql)

        if not exec_result.success:
            # SQL syntax error - trả về message thân thiện
            friendly_msg = await self._generate_friendly_error(
                question, exec_result.error, prep.language
            )
            return ChatSqlFullResult(
                success=True,
                sql=sql_result.sql,
                natural_response=friendly_msg,
            )

        # Bước 3: Format response
        natural_response = await self.format_response(
            question=question,
            sql=sql_result.sql,
            data=exec_result.data,
            row_count=exec_result.row_count,
            language=prep.language,
        )

        return ChatSqlFullResult(
            success=True,
            mode="SEARCH",
            sql=sql_result.sql,
            data=exec_result.data,
            row_count=exec_result.row_count,
            natural_response=natural_response,
        )

    async def _generate_friendly_error(
        self, question: str, error: str, language: str = "vi"
    ) -> str:
        """Sinh message thân thiện khi không thể xử lý câu hỏi."""
        prompt = f"""Bạn là trợ lý AI thân thiện. Người dùng đã hỏi một câu hỏi mà hệ thống không thể xử lý.

Câu hỏi: {question}
Lý do: {error[:200]}

Hãy trả lời thân thiện bằng {"tiếng Việt" if language == "vi" else "English"}:
- Giải thích nhẹ nhàng rằng bạn không hiểu hoặc câu hỏi không liên quan đến dữ liệu
- Gợi ý các câu hỏi mẫu phù hợp (về khóa học, học viên, doanh thu, tiến độ học...)
- Giữ ngắn gọn, thân thiện (2-3 câu)

KHÔNG đề cập technical error hay SQL.
"""
        try:
            response = await self.llm_service.call_model(
                prompt=prompt,
                mime_type="text/plain",
                temperature=0.7,
                max_output_tokens=300,
            )
            return (
                response.strip() if response else self._default_error_message(language)
            )
        except Exception:
            return self._default_error_message(language)

    def _default_error_message(self, language: str = "vi") -> str:
        """Message mặc định khi không thể sinh response."""
        if language == "vi":
            return "Xin lỗi, tôi chưa hiểu câu hỏi của bạn. Bạn có thể hỏi về: khóa học của tôi, tiến độ học, doanh thu, hoặc số học viên."
        return "Sorry, I didn't understand your question. You can ask about: my courses, learning progress, revenue, or student count."


# =========================
# FASTAPI DEPENDENCY
# =========================


_text_to_sql_service: Optional[TextToSqlService] = None


def get_text_to_sql_service(
    llm_service: LLMService = Depends(LLMService),
) -> TextToSqlService:
    global _text_to_sql_service
    if _text_to_sql_service is None:
        _text_to_sql_service = TextToSqlService(llm_service=llm_service)
    return _text_to_sql_service
