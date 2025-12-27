from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.shares.paypal_service import PayPalService
from app.services.user.message_classifier import (
    MessageClassifierService,
    get_message_classifier_service,
    normalize_text,
    rule_decide,
)

router = APIRouter(prefix="/test", tags=["test"])


# =========================
# MESSAGE CLASSIFIER TEST
# =========================


class ClassifyRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, Any]]] = None
    has_prev_context: bool = False


class RuleDecideRequest(BaseModel):
    message: str
    has_prev_context: bool = False


@router.post("/classify")
async def test_classify_message(
    body: ClassifyRequest,
    classifier: MessageClassifierService = Depends(get_message_classifier_service),
):
    """
    Test classify_message của MessageClassifierService.

    Returns:
        mode: NO_SEARCH | REUSE | SEARCH
        normalized_message: message đã chuẩn hóa
        has_prev_context: có context trước không
    """
    result = await classifier.classify_message(
        message=body.message,
        chat_history=body.chat_history,
        has_prev_context=body.has_prev_context,
    )
    return {
        "input": {
            "message": body.message,
            "has_prev_context": body.has_prev_context,
            "chat_history_count": len(body.chat_history) if body.chat_history else 0,
        },
        "result": result,
    }


@router.post("/rule-decide")
async def test_rule_decide(body: RuleDecideRequest):
    """
    Test rule_decide (chỉ rule, không gọi LLM).

    Returns:
        mode: NO_SEARCH | REUSE | SEARCH | None (nếu mơ hồ)
    """
    normalized = normalize_text(body.message)
    mode = rule_decide(body.message, body.has_prev_context)

    return {
        "input": {
            "message": body.message,
            "normalized": normalized,
            "has_prev_context": body.has_prev_context,
        },
        "mode": mode,
        "note": (
            "None = mơ hồ, cần gọi LLM" if mode is None else "Xác định được bằng rule"
        ),
    }


@router.get("/normalize")
async def test_normalize(text: str = Query(...)):
    """
    Test normalize_text.
    """
    return {
        "input": text,
        "normalized": normalize_text(text),
    }


@router.get("/batch-test")
async def batch_test_rule_decide():
    """
    Chạy hàng trăm test cases cùng lúc.
    Trả về tổng hợp pass/fail.
    """
    # Test cases: (message, has_prev_context, expected_mode)
    test_cases = [
        # ========== NO_SEARCH (giao tiếp xã giao) ==========
        ("hello", False, "NO_SEARCH"),
        ("hi", False, "NO_SEARCH"),
        ("hey", False, "NO_SEARCH"),
        ("chào", False, "NO_SEARCH"),
        ("chào bạn", False, "NO_SEARCH"),
        ("xin chào", False, "NO_SEARCH"),
        ("cảm ơn", False, "NO_SEARCH"),
        ("cảm ơn bạn", True, "NO_SEARCH"),
        ("thanks", False, "NO_SEARCH"),
        ("thank you", True, "NO_SEARCH"),
        ("ok", False, "NO_SEARCH"),
        ("oke", False, "NO_SEARCH"),
        ("okay got it", True, "NO_SEARCH"),
        ("được rồi", True, "NO_SEARCH"),
        ("hiểu rồi", True, "NO_SEARCH"),
        ("haha", False, "NO_SEARCH"),
        ("lol", False, "NO_SEARCH"),
        ("tuyệt vời", True, "NO_SEARCH"),
        ("bye", False, "NO_SEARCH"),
        ("goodbye", False, "NO_SEARCH"),
        # ========== REUSE (hỏi tiếp ý trước) - CÓ CONTEXT ==========
        ("giải thích thêm đi", True, "REUSE"),
        ("giải thích rõ hơn", True, "REUSE"),
        ("nói rõ hơn đi", True, "REUSE"),
        ("nói thêm đi", True, "REUSE"),
        ("chi tiết hơn được không?", True, "REUSE"),
        ("cụ thể hơn đi", True, "REUSE"),
        ("ví dụ thêm", True, "REUSE"),
        ("cho ví dụ đi", True, "REUSE"),
        ("ý đó là sao?", True, "REUSE"),
        ("đoạn đó nghĩa là gì?", True, "REUSE"),
        ("cái đó hoạt động thế nào?", True, "REUSE"),
        ("phần trên là sao?", True, "REUSE"),
        ("mình chưa hiểu", True, "REUSE"),
        ("chưa hiểu lắm", True, "REUSE"),
        ("không hiểu", True, "REUSE"),
        ("sao vậy?", True, "REUSE"),
        ("tại sao vậy?", True, "REUSE"),
        ("tức là sao?", True, "REUSE"),
        ("??", True, "REUSE"),
        ("???", True, "REUSE"),
        ("?", True, "REUSE"),
        ("hả?", True, "REUSE"),
        ("sao?", True, "REUSE"),
        ("gì?", True, "REUSE"),
        ("explain more", True, "REUSE"),
        ("tell me more", True, "REUSE"),
        ("more details please", True, "REUSE"),
        ("what do you mean?", True, "REUSE"),
        ("i dont understand", True, "REUSE"),
        ("elaborate", True, "REUSE"),
        ("tiếp đi", True, "REUSE"),
        ("tiếp tục đi", True, "REUSE"),
        ("rồi sao nữa?", True, "REUSE"),
        # ========== SEARCH (kiến thức mới) - KHÔNG CÓ CONTEXT ==========
        ("React hook là gì?", False, "SEARCH"),
        ("định nghĩa machine learning", False, "SEARCH"),
        ("công thức tính diện tích hình tròn", False, "SEARCH"),
        ("Docker là gì và tại sao nên dùng?", False, "SEARCH"),
        ("giải thích về async await trong JavaScript", False, "SEARCH"),
        ("how does useState work in React?", False, "SEARCH"),
        ("what is dependency injection?", False, "SEARCH"),
        ("explain microservices architecture", False, "SEARCH"),
        ("hướng dẫn cài đặt Node.js trên Ubuntu", False, "SEARCH"),
        ("so sánh SQL và NoSQL database", False, "SEARCH"),
        # ========== EDGE CASES ==========
        ("??", False, "NO_SEARCH"),  # không có context → linh tinh
        ("ok thanks", False, "NO_SEARCH"),
        ("nice thanks", True, "NO_SEARCH"),
        # THÊM NHIỀU TEST CASES
        # NO_SEARCH - thêm
        ("cam on nhieu", False, "NO_SEARCH"),
        ("tuyệt", False, "NO_SEARCH"),
        ("perfect", True, "NO_SEARCH"),
        ("great job", True, "NO_SEARCH"),
        ("da hieu", True, "NO_SEARCH"),
        ("ro roi", True, "NO_SEARCH"),
        # REUSE - thêm
        ("chi tiết hơn nữa", True, "REUSE"),
        ("cái này có nghĩa là gì?", True, "REUSE"),
        ("tức là như thế nào?", True, "REUSE"),
        ("vậy là sao?", True, "REUSE"),
        ("rồi sao?", True, "REUSE"),
        ("why?", True, "REUSE"),
        ("how?", True, "REUSE"),
        ("clarify please", True, "REUSE"),
        ("can you explain more?", True, "REUSE"),
        ("ví dụ cụ thể đi", True, "REUSE"),
        ("cho mình ví dụ", True, "REUSE"),
        # SEARCH - thêm
        ("Kubernetes deployment là gì?", False, "SEARCH"),
        ("giải thích về Spring Boot security", False, "SEARCH"),
        ("Redis cache hoạt động như thế nào?", False, "SEARCH"),
        ("MongoDB schema design best practices", False, "SEARCH"),
        ("TypeScript generics tutorial", False, "SEARCH"),
        ("Golang concurrency patterns", False, "SEARCH"),
        ("Python decorator là gì?", False, "SEARCH"),
        ("Java stream API tutorial", False, "SEARCH"),
        ("hướng dẫn sử dụng Docker compose", False, "SEARCH"),
        ("cách tạo REST API với Node.js", False, "SEARCH"),
        # EDGE: có context nhưng hỏi kiến thức mới
        ("còn Spring Security thì sao?", True, "SEARCH"),
        ("thế React context là gì?", True, "SEARCH"),
    ]

    results = []
    passed = 0
    failed = 0

    for msg, ctx, expected in test_cases:
        mode = rule_decide(msg, ctx)
        normalized = normalize_text(msg)

        # None cũng có thể đúng nếu expected là None
        is_pass = mode == expected

        if is_pass:
            passed += 1
        else:
            failed += 1
            results.append(
                {
                    "message": msg,
                    "normalized": normalized,
                    "has_prev_context": ctx,
                    "expected": expected,
                    "actual": mode,
                    "status": "❌ FAIL",
                }
            )

    return {
        "summary": {
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / len(test_cases) * 100):.1f}%",
        },
        "failed_cases": results,
    }


@router.get("/mega-test")
async def mega_test_rule_decide(count: int = Query(default=10000, le=50000)):
    """
    Generate và test hàng nghìn cases tự động.
    Tạo variations từ các template cơ bản.
    """
    import random

    # ========== TEMPLATES ==========
    # NO_SEARCH templates
    no_search_templates = [
        "hello",
        "hi",
        "hey",
        "chào",
        "xin chào",
        "chào bạn",
        "cảm ơn",
        "cảm ơn bạn",
        "cảm ơn nhé",
        "thanks",
        "thank you",
        "tks",
        "ok",
        "oke",
        "okay",
        "được",
        "được rồi",
        "hiểu rồi",
        "đã hiểu",
        "tốt",
        "hay",
        "tuyệt",
        "tuyệt vời",
        "nice",
        "great",
        "good",
        "perfect",
        "haha",
        "hihi",
        "lol",
        "bye",
        "goodbye",
        "see you",
        "ok thanks",
        "nice thanks",
        "got it",
        "alright",
        "fine",
        "sure",
    ]

    # REUSE templates (cần has_prev_context=True)
    reuse_templates = [
        "giải thích thêm",
        "giải thích rõ hơn",
        "nói rõ hơn",
        "nói thêm đi",
        "chi tiết hơn",
        "cụ thể hơn",
        "ví dụ thêm",
        "cho ví dụ",
        "ý đó là sao",
        "đoạn đó nghĩa là gì",
        "cái đó hoạt động thế nào",
        "mình chưa hiểu",
        "chưa hiểu lắm",
        "không hiểu",
        "sao vậy",
        "tại sao vậy",
        "tức là sao",
        "rồi sao",
        "explain more",
        "tell me more",
        "more details",
        "what do you mean",
        "i dont understand",
        "elaborate",
        "clarify",
        "tiếp đi",
        "tiếp tục",
        "rồi sao nữa",
        "còn gì nữa",
    ]

    # REUSE short (cần has_prev_context=True)
    reuse_short = ["??", "???", "?", "hả?", "sao?", "gì?", "why?", "how?", "what?"]

    # SEARCH templates (cần has_prev_context=False)
    tech_terms = [
        "React",
        "Node.js",
        "Python",
        "JavaScript",
        "TypeScript",
        "Docker",
        "Kubernetes",
        "Redis",
        "MongoDB",
        "PostgreSQL",
        "MySQL",
        "Spring Boot",
        "Java",
        "Golang",
        "Rust",
        "C++",
        "Vue.js",
        "Angular",
        "Next.js",
        "GraphQL",
        "REST API",
        "Microservices",
        "AWS",
        "Azure",
        "GCP",
        "Machine Learning",
        "Deep Learning",
        "Neural Network",
        "TensorFlow",
        "PyTorch",
        "FastAPI",
        "Django",
        "Flask",
        "Express.js",
        "NestJS",
    ]

    search_patterns = [
        "{tech} là gì?",
        "định nghĩa {tech}",
        "{tech} hoạt động như thế nào?",
        "hướng dẫn cài đặt {tech}",
        "so sánh {tech} và {tech2}",
        "cách sử dụng {tech} trong dự án",
        "{tech} tutorial cho người mới",
        "best practices khi dùng {tech}",
        "how does {tech} work?",
        "what is {tech}?",
        "explain {tech} architecture",
        "{tech} vs {tech2} comparison",
        "giải thích về {tech}",
        "công thức {tech}",
    ]

    # VIDEO/LESSON patterns (SEARCH - cần query nội dung video)
    video_patterns = [
        "video này nói về gì?",
        "tóm tắt video",
        "tóm tắt bài học",
        "bài học này dạy gì?",
        "nội dung chính của video là gì?",
        "phút thứ {time} nói về gì?",
        "giảng viên nói gì về {topic}?",
        "video có đề cập đến {topic} không?",
        "phần nào trong video nói về {topic}?",
        "giải thích đoạn phút {time}",
        "ý chính của bài học là gì?",
        "các điểm quan trọng trong video",
        "giảng viên demo gì trong bài này?",
        "code mẫu trong video là gì?",
        "bài tập cuối bài là gì?",
        "what does this video cover?",
        "summarize this lesson",
        "what is the main topic?",
        "explain the concept at {time}",
        "what does the instructor say about {topic}?",
    ]

    video_topics = [
        "React hooks",
        "state management",
        "API calls",
        "database design",
        "authentication",
        "deployment",
        "testing",
        "performance",
        "security",
        "caching",
        "microservices",
        "Docker containers",
    ]

    video_times = ["2:30", "5:00", "10:15", "15:00", "20:30", "3", "7", "12"]

    # ========== GENERATE CASES ==========
    test_cases = []
    cases_per_category = count // 3

    # 1) NO_SEARCH cases
    for _ in range(cases_per_category):
        msg = random.choice(no_search_templates)
        # Random variations
        if random.random() > 0.7:
            msg = msg.upper() if random.random() > 0.5 else msg.capitalize()
        if random.random() > 0.8:
            msg += random.choice(["!", "!!", " nha", " nhé", " bạn"])
        ctx = random.choice([True, False])
        test_cases.append((msg, ctx, "NO_SEARCH"))

    # 2) REUSE cases (với context)
    for _ in range(cases_per_category):
        if random.random() > 0.3:
            msg = random.choice(reuse_templates)
            if random.random() > 0.7:
                msg += random.choice(["?", " đi", " được không?", " nhé"])
        else:
            msg = random.choice(reuse_short)
        test_cases.append((msg, True, "REUSE"))  # phải có context

    # 3) SEARCH cases - tech (không có context)
    for _ in range(cases_per_category // 2):
        pattern = random.choice(search_patterns)
        tech = random.choice(tech_terms)
        tech2 = random.choice([t for t in tech_terms if t != tech])
        msg = pattern.format(tech=tech, tech2=tech2)
        if random.random() > 0.8:
            msg = msg.lower()
        test_cases.append((msg, False, "SEARCH"))

    # 4) SEARCH cases - video/lesson (không có context)
    for _ in range(cases_per_category // 2):
        pattern = random.choice(video_patterns)
        topic = random.choice(video_topics)
        time = random.choice(video_times)
        msg = pattern.format(topic=topic, time=time)
        if random.random() > 0.8:
            msg = msg.lower()
        test_cases.append((msg, False, "SEARCH"))

    # Shuffle
    random.shuffle(test_cases)

    # ========== RUN TESTS ==========
    passed = 0
    failed = 0
    failed_samples = []

    for msg, ctx, expected in test_cases:
        mode = rule_decide(msg, ctx)
        if mode == expected:
            passed += 1
        else:
            failed += 1
            # Chỉ lưu 50 failed samples đầu tiên
            if len(failed_samples) < 50:
                failed_samples.append(
                    {
                        "message": msg,
                        "normalized": normalize_text(msg),
                        "has_prev_context": ctx,
                        "expected": expected,
                        "actual": mode,
                    }
                )

    # ========== ANALYSIS ==========
    # Đếm theo category
    by_expected = {
        "NO_SEARCH": {"pass": 0, "fail": 0},
        "REUSE": {"pass": 0, "fail": 0},
        "SEARCH": {"pass": 0, "fail": 0},
    }
    for msg, ctx, expected in test_cases:
        mode = rule_decide(msg, ctx)
        if mode == expected:
            by_expected[expected]["pass"] += 1
        else:
            by_expected[expected]["fail"] += 1

    return {
        "summary": {
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / len(test_cases) * 100):.2f}%",
        },
        "by_category": {
            k: {
                "total": v["pass"] + v["fail"],
                "passed": v["pass"],
                "failed": v["fail"],
                "pass_rate": (
                    f"{(v['pass'] / (v['pass'] + v['fail']) * 100):.1f}%"
                    if v["pass"] + v["fail"] > 0
                    else "N/A"
                ),
            }
            for k, v in by_expected.items()
        },
        "failed_samples": failed_samples[:50],  # Chỉ 50 samples
    }


@router.get("/payout")
async def test_payout(
    request: Request,
):
    paypal_service = PayPalService(http=request.app.state.http)
    return await paypal_service.payout(
        receiver_email="sb-euk47j43769608@personal.example.com",
        amount="10.00",
        currency="USD",
        note="Test payout",
    )


@router.get("/get_payout_status")
async def get_payout_status(
    request: Request,
    payout_batch_id: str = Query(...),
):
    paypal_service = PayPalService(http=request.app.state.http)
    return await paypal_service.get_payout_status(payout_batch_id=payout_batch_id)


# =========================
# TUTOR CHAT TEST (no auth)
# =========================

from uuid import UUID

from app.services.user.tutor_chat import TutorChatService, get_tutor_chat_service


@router.get("/tutor-chat/check-service")
async def check_tutor_chat_service(
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Kiểm tra TutorChatService có khởi tạo được không.
    """
    return {
        "status": "ok",
        "service": str(type(service)),
        "methods": [
            "validate_enrollment",
            "validate_lesson_access",
            "get_threads_by_lesson",
            "get_active_thread",
            "get_thread_by_id",
            "create_new_thread",
            "choose_thread",
            "deactivate_thread",
            "delete_thread",
        ],
    }


@router.get("/tutor-chat/test-validation")
async def test_validation(
    user_id: UUID = Query(...),
    lesson_id: UUID = Query(...),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Test validate_lesson_access.
    """
    try:
        result = await service.validate_lesson_access(user_id, lesson_id)
        return {
            "status": "passed",
            "lesson": {
                "id": str(result["lesson"].id),
                "title": result["lesson"].title,
            },
            "course": {
                "id": str(result["course"].id),
                "title": result["course"].title,
            },
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
        }


@router.get("/tutor-chat/test-list")
async def test_list_threads(
    user_id: UUID = Query(...),
    lesson_id: UUID = Query(...),
    limit: int = Query(10),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Test get_threads_by_lesson.
    """
    try:
        return await service.get_threads_by_lesson(
            user_id=user_id,
            lesson_id=lesson_id,
            limit=limit,
        )
    except Exception as e:
        return {"error": str(e)}


@router.post("/tutor-chat/test-create")
async def test_create_thread(
    user_id: UUID = Query(...),
    lesson_id: UUID = Query(...),
    title: str = Query("Test Thread"),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Test create_new_thread.
    """
    try:
        return await service.create_new_thread(
            user_id=user_id,
            lesson_id=lesson_id,
            title=title,
        )
    except Exception as e:
        return {"error": str(e)}


# Test chat message
from app.services.user.tutor_chat_message import (
    TutorChatMessageService,
    get_tutor_chat_message_service,
)


class TestSendMessageRequest(BaseModel):
    user_id: UUID
    lesson_id: UUID
    message: str
    images: Optional[List[Dict[str, Any]]] = None


@router.post("/tutor-chat/test-send")
async def test_send_message(
    body: TestSendMessageRequest,
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Test send_message (không cần auth).
    Payload: {
        "user_id": "...",
        "lesson_id": "...",
        "message": "...",
        "images": [{"url": "...", "file_size": 100, "mime_type": "image/png"}]
    }
    """
    try:
        return await service.send_message(
            user_id=body.user_id,
            lesson_id=body.lesson_id,
            message=body.message,
            images=body.images,
        )
    except Exception as e:
        import traceback

        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/tutor-chat/test-messages")
async def test_get_messages(
    user_id: UUID = Query(...),
    thread_id: UUID = Query(...),
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Test get_messages (không cần auth).
    """
    try:
        return await service.get_messages(
            user_id=user_id,
            thread_id=thread_id,
        )
    except Exception as e:
        return {"error": str(e)}


@router.post("/tutor-chat/test-upload")
async def test_upload_image(
    files: List[UploadFile] = File(..., alias="file"),
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Test upload & OCR multiple images (Requires Auth).
    """
    try:
        user: User = await auth.get_current_user()
        results = await service.upload_and_ocr_images(user_id=user.id, files=files)
        if not results:
            return {"error": "Failed"}
        return results
    except Exception as e:
        import traceback

        return {"error": str(e), "traceback": traceback.format_exc()}
