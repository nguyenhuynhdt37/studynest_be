# app/services/user/message_classifier.py
"""
MessageClassifierService - Phân loại câu hỏi cho chat học tập.

Mục tiêu:
- Không phải câu nào cũng đi tìm tài liệu (tốn tiền, chậm).
- Câu hỏi kiểu "ý đó", "giải thích thêm" phải dùng lại context vừa tìm.

Chiến lược:
1) Rule (ưu tiên): nhanh, rẻ
2) Gọi model phân loại (fallback): chỉ khi mơ hồ

Kết quả mode:
- NO_SEARCH: giao tiếp linh tinh / không cần tìm tài liệu
- REUSE: hỏi tiếp ý trước / dùng lại context cũ (đã tìm ở câu trước)
- SEARCH: hỏi kiến thức mới / cần tìm tài liệu mới
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends

from app.core.llm import LLMService

Mode = Literal["NO_SEARCH", "REUSE", "SEARCH"]


# =========================
# KEYWORDS (đã normalize sẵn: lowercase + không dấu)
# =========================

SMALL_TALK: List[str] = [
    # VN
    "chao",
    "xin chao",
    "chao ban",
    "cam on",
    "cam on ban",
    "cam on nhe",
    "ok",
    "oke",
    "okay",
    "okie",
    "duoc",
    "duoc roi",
    "dc roi",
    "hieu roi",
    "da hieu",
    "ro roi",
    "tot",
    "hay",
    "tuyet",
    "tuyet voi",
    "haha",
    "hihi",
    "lol",
    "ok thanks",
    "nice thanks",
    # EN
    "hello",
    "hi",
    "hey",
    "yo",
    "thanks",
    "thank",
    "thank you",
    "tks",
    "ty",
    "nice",
    "great",
    "good",
    "awesome",
    "amazing",
    "perfect",
    "got it",
    "i see",
    "alright",
    "fine",
    "sure",
    "yep",
    "yup",
    "yeah",
    "bye",
    "goodbye",
    "see you",
    "later",
    "okay got it",
]

FOLLOW_UP: List[str] = [
    # VN
    "y do",
    "y tren",
    "y nay",
    "doan do",
    "doan tren",
    "cai do",
    "cai nay",
    "phan do",
    "phan tren",
    "noi ro hon",
    "noi ro",
    "noi them",
    "noi tiep",
    "tiep di",
    "tiep tuc",
    "them nua",
    "gi nua",
    "giai thich them",
    "giai thich ro hon",
    "giai thich ro",
    "giai thich lai",
    "giai thich ki hon",
    "chi tiet hon",
    "chi tiet them",
    "cu the hon",
    "cu the",
    "ro hon",
    "vi du them",
    "them vi du",
    "cho vi du",
    "minh chua hieu",
    "chua hieu",
    "khong hieu",
    "ko hieu",
    "chua ro",
    "khong ro",
    "tai sao vay",
    "sao vay",
    "the la sao",
    "nghia la gi",
    "co nghia gi",
    "lam sao",
    "bang cach nao",
    "nhu the nao",
    "the nao",
    "tuc la sao",
    "tuc la",
    "roi sao",
    "roi sao nua",
    "tiep i",
    "tiep tuc i",
    # EN
    "explain more",
    "more detail",
    "more details",
    "more details please",
    "elaborate",
    "can you explain",
    "tell me more",
    "go on",
    "continue",
    "what do you mean",
    "what does that mean",
    "i dont understand",
    "i don't understand",
    "dont get it",
    "dont understand",
    "why is that",
    "why so",
    "how so",
    "how come",
    "for example",
    "give example",
    "example please",
    "another example",
    "clarify",
    "be more specific",
    "specifically",
]

# Câu siêu ngắn mơ hồ (thường là hỏi tiếp nếu có context)
AMBIGUOUS_SHORT: List[str] = [
    # VN
    "sao",
    "sao?",
    "ha",
    "ha?",
    "gi",
    "gi?",
    "the",
    "do",
    "roi sao",
    "vay sao",
    "sao ta",
    "gi vay",
    "gi the",
    "gi day",
    # EN
    "why",
    "why?",
    "what",
    "what?",
    "how",
    "how?",
    "huh",
    "hmm",
    "uh",
    "uhh",
    # symbols
    "?",
    "??",
    "???",
    "!?",
    "!!",
    "!",
]

# dùng set cho match chính xác nhanh
AMBIGUOUS_SHORT_SET = set(AMBIGUOUS_SHORT)


# =========================
# TEXT NORMALIZATION
# =========================


def normalize_text(s: str) -> str:
    """
    Chuẩn hóa để so keyword:
    - lower
    - chuyển đ/Đ → d
    - bỏ dấu tiếng Việt
    - giữ chữ/số/khoảng trắng/?/!
    - gom khoảng trắng
    """
    if not s:
        return ""

    s = s.strip().lower()

    # Xử lý các ký tự đặc biệt phổ biến
    s = s.replace("c++", "cpp").replace("c#", "csharp")  # tech terms
    s = s.replace("đ", "d").replace("Đ", "d")  # tiếng Việt

    # Bỏ dấu tiếng Việt (NFD decomposition)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

    # giữ a-z 0-9 space ? !
    s = re.sub(r"[^a-z0-9\s\?\!]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _match_keyword(text: str, kw: str) -> bool:
    """
    Match keyword theo "ranh giới từ" an toàn hơn `kw in text`.
    - kw có thể có khoảng trắng (cụm từ)
    - kw có thể là "??" hoặc "!" -> match chứa
    """
    kw = kw.strip()
    if not kw:
        return False

    # keyword chỉ toàn dấu ?! thì match chứa là đủ
    if all(ch in "?! " for ch in kw):
        return kw in text

    escaped = re.escape(kw)
    # (?<!\w) ... (?!\w) tránh match bậy kiểu ok trong book
    return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None


def contains_any(text: str, keywords: List[str]) -> bool:
    for kw in keywords:
        if _match_keyword(text, kw):
            return True
    return False


# =========================
# RULE DECISION
# =========================


def rule_decide(message: str, has_prev_context: bool) -> Optional[Mode]:
    """
    Rule-based với hệ thống scoring:
    - Tính điểm cho mỗi mode (NO_SEARCH, REUSE, SEARCH)
    - So sánh điểm để quyết định
    - Trả None nếu mơ hồ để fallback LLM
    """
    m = normalize_text(message)
    if not m:
        return "NO_SEARCH"

    # ====== score ======
    no_s = 0  # NO_SEARCH score
    reu_s = 0  # REUSE score
    sea_s = 0  # SEARCH score

    # 1) giao tiếp: câu rất ngắn + từ xã giao
    if len(m) <= 25 and contains_any(m, SMALL_TALK):
        no_s += 4

    # 2) dấu hiệu "hỏi tiếp"
    # (a) từ chỉ trỏ / tham chiếu
    if re.search(r"(?<!\w)(do|day|nay|kia|tren|duoi|doan|phan|cai)(?!\w)", m):
        reu_s += 2

    # (b) cụm "giải thích / nói rõ / ý là / tức là / chưa hiểu"
    if re.search(
        r"(giai thich|noi ro|y la|tuc la|noi them|chi tiet|cu the|chua hieu|khong hieu|ko hieu|vi du|explain|elaborate|more detail|tell me more|what do you mean|dont understand)",
        m,
    ):
        reu_s += 4

    # (c) câu chỉ toàn ?! (vd: ?? hoặc ???)
    if re.fullmatch(r"[\?\!]+", m):
        if has_prev_context:
            reu_s += 4
        else:
            no_s += 3  # không có context → coi như linh tinh

    # (d) câu rất ngắn + có ?
    if len(m) <= 10 and "?" in m:
        reu_s += 2

    # (e) match các short ambiguous keywords
    if m in AMBIGUOUS_SHORT_SET:
        reu_s += 2

    # (f) các keyword follow-up phổ biến
    if contains_any(m, FOLLOW_UP):
        reu_s += 3

    # 3) dấu hiệu "hỏi kiến thức mới"
    # có từ để hỏi + có nội dung
    if re.search(
        r"(la gi|dinh nghia|cong thuc|huong dan|cai dat|how to|how does|what is|define|explain.*architecture|compare|so sanh)",
        m,
    ):
        sea_s += 4

    # có từ liên quan video/lesson
    if re.search(
        r"(video|bai hoc|giang vien|tom tat|phut thu|noi dung chinh|y chinh|diem quan trong|"
        r"doan phut|phut \d|concept at|lesson|instructor|summarize|main topic|this video|cover|demo)",
        m,
    ):
        sea_s += 4

    # có nhiều từ kỹ thuật (heuristic): có từ kiểu tech
    tech_match = re.search(
        r"(react|node|python|javascript|typescript|docker|kubernetes|sql|nosql|mysql|postgresql|"
        r"api|database|async|await|hook|component|java|spring|golang|redis|mongodb|"
        r"flask|django|fastapi|angular|vue|nestjs|express|graphql|microservices|"
        r"aws|azure|gcp|machine learning|deep learning|neural network|tensorflow|pytorch|"
        r"rust|cpp|csharp|laravel|php|ruby|rails|next|nuxt|webpack|vite|git|linux|devops|"
        r"rest|grpc|websocket|kafka|rabbitmq|elasticsearch|nginx|apache)",
        m,
    )
    if tech_match:
        sea_s += 3
        # có tech term + không có context → rất có thể hỏi kiến thức mới
        if not has_prev_context:
            sea_s += 2

    # có ký tự đặc biệt code: _ :: () []
    if re.search(r"[_::\(\)\[\]]", m):
        sea_s += 1

    # câu dài (>= 18 ký tự) mà không có dấu hiệu REUSE -> có thể là câu hỏi mới
    if len(m) >= 18 and reu_s == 0 and no_s == 0:
        sea_s += 2

    # ====== quyết định ======
    # nếu không có context thì REUSE khó đúng -> giảm mạnh
    if not has_prev_context:
        reu_s = max(0, reu_s - 3)

    # ưu tiên mạnh: nếu REUSE cao và có context
    if has_prev_context and reu_s >= 3 and reu_s > sea_s:
        return "REUSE"

    # NO_SEARCH nếu điểm cao
    if no_s >= 3 and no_s > sea_s:
        return "NO_SEARCH"

    # SEARCH nếu điểm cao
    if sea_s >= 3:
        return "SEARCH"

    # mơ hồ -> fallback LLM
    return None


# =========================
# LLM FALLBACK (chỉ khi mơ hồ)
# =========================


async def llm_classify_mode(
    message: str,
    last_messages: List[str],
    llm_service: LLMService,
) -> Mode:
    """
    Gọi model nhỏ để phân loại.
    last_messages: chỉ cần 1-2 câu gần nhất (đủ cho "ý đó" / "đoạn đó")
    """
    history = "\n".join(last_messages[-2:]) if last_messages else "(khong co)"

    prompt = f"""
Ban la bo phan loai cau hoi cho he thong hoc tap.

Ngu canh chat truoc:
{history}

Cau hoi hien tai:
{message}

Chon DUY NHAT 1 nhan:
- NO_SEARCH: chao hoi, cam on, giao tiep xa giao, khong can tim tai lieu
- REUSE: hoi tiep y cau truoc, muon giai thich them/vi du them, dung lai context cu
- SEARCH: hoi kien thuc moi, can tim tai lieu moi

Chi tra ve dung 1 nhan (NO_SEARCH hoac REUSE hoac SEARCH). KHONG giai thich.
""".strip()

    try:
        result = await llm_service.generate_text(prompt)
        out = (result or "").strip().upper()

        if out in ("NO_SEARCH", "REUSE", "SEARCH"):
            return out  # type: ignore

        # nếu model lỡ trả dài, cố gắng bóc nhãn
        if "NO_SEARCH" in out:
            return "NO_SEARCH"
        if "REUSE" in out:
            return "REUSE"
        if "SEARCH" in out:
            return "SEARCH"

        return "SEARCH"
    except Exception:
        return "SEARCH"


async def decide_mode(
    message: str,
    has_prev_context: bool,
    last_messages: List[str],
    llm_service: LLMService,
) -> Mode:
    """
    Quyết định cuối:
    - rule trước
    - mơ hồ -> gọi model phân loại
    """
    mode = rule_decide(message, has_prev_context)
    if mode is not None:
        return mode
    return await llm_classify_mode(message, last_messages, llm_service)


# =========================
# SERVICE
# =========================


class MessageClassifierService:
    """
    Service phân loại câu hỏi - chỉ làm nhiệm vụ classify.
    Xử lý từng mode sẽ làm ở service khác.
    """

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def preprocess_message(self, message: str) -> str:
        """Tiền xử lý message trước khi classify."""
        message = (message or "").strip()
        message = re.sub(r"\s+", " ", message)
        return message

    async def classify_message(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        has_prev_context: bool = False,
    ) -> Dict[str, Any]:
        """
        Phân loại message thành NO_SEARCH | REUSE | SEARCH.

        Args:
            message: câu user
            chat_history: để fallback model hiểu ngữ cảnh
            has_prev_context: có context từ lần search trước không

        Returns:
            {
                "mode": "NO_SEARCH" | "REUSE" | "SEARCH",
                "normalized_message": str,
                "has_prev_context": bool,
            }
        """
        last_messages: List[str] = []
        if chat_history:
            for msg in chat_history[-4:]:
                content = (msg or {}).get("content", "")
                if content:
                    last_messages.append(str(content))

        mode = await decide_mode(
            message=message,
            has_prev_context=has_prev_context,
            last_messages=last_messages,
            llm_service=self.llm_service,
        )

        return {
            "mode": mode,
            "normalized_message": normalize_text(message),
            "has_prev_context": has_prev_context,
        }

    # =========================
    # HELPERS
    # =========================

    def should_search(self, mode: Mode) -> bool:
        """Mode cần tìm tài liệu mới."""
        return mode == "SEARCH"

    def should_reuse_context(self, mode: Mode) -> bool:
        """Mode dùng lại context cũ."""
        return mode == "REUSE"

    def is_casual_chat(self, mode: Mode) -> bool:
        """Mode giao tiếp xã giao."""
        return mode == "NO_SEARCH"


# =========================
# FASTAPI DEPENDENCY
# =========================

_message_classifier_service: Optional[MessageClassifierService] = None


def get_message_classifier_service(
    llm_service: LLMService = Depends(LLMService),
) -> MessageClassifierService:
    global _message_classifier_service
    if _message_classifier_service is None:
        _message_classifier_service = MessageClassifierService(llm_service=llm_service)
    return _message_classifier_service
