import re
import unicodedata


def generate_slug(title: str) -> str:
    """
    ✅ Sinh slug thân thiện từ title
    - Loại bỏ dấu tiếng Việt
    - Giữ lại chữ cái, số, dấu gạch ngang
    - Viết thường
    """
    if not title:
        return ""

    # 1️⃣ Chuẩn hoá unicode (tách dấu)
    normalized = unicodedata.normalize("NFD", title)

    # 2️⃣ Loại bỏ ký tự dấu (accent)
    no_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # 3️⃣ Chuyển sang chữ thường
    text = no_accents.lower()

    # 4️⃣ Thay khoảng trắng & ký tự đặc biệt bằng dấu gạch ngang
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # 5️⃣ Bỏ dấu gạch đầu/cuối và gộp gạch liên tiếp
    text = re.sub(r"-{2,}", "-", text).strip("-")

    return text
