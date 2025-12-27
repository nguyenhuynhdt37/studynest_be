import re
from pathlib import Path


def camel_to_snake(name: str) -> str:
    """Chuyển CamelCase → snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def fix_sqlacodegen_file(filepath: str):
    """
    ✅ Phiên bản an toàn (2025):
    - Chuyển kế thừa (trừ Base) → Base.
    - Tự động thêm relationship() 1–1 hai chiều.
    - Không chèn trùng nếu đã có.
    - Không chạm vào class Base.
    """
    text = Path(filepath).read_text(encoding="utf-8")

    # ⚙️ Loại bỏ indent sai (khi ForeignKeyConstraint bị lùi vào sai block)
    text = re.sub(r"\n\s{8,}ForeignKeyConstraint", "\n    ForeignKeyConstraint", text)

    # tìm tất cả class con kế thừa class cha
    pattern = re.compile(r"class\s+(\w+)\((\w+)\):")
    matches = pattern.findall(text)

    # tránh trùng quan hệ bằng set
    added_relations = set()

    for child, parent in matches:
        if parent.lower() == "base" or child.lower() == "base":
            continue

        # 1️⃣ Đổi kế thừa về Base
        text = re.sub(
            rf"class {child}\({parent}\):",
            f"class {child}(Base):",
            text,
        )

        parent_field = camel_to_snake(parent)
        child_field = camel_to_snake(child)

        # regex lấy toàn bộ block class (kể cả nhiều dòng)
        def find_block(name: str):
            m = re.search(
                rf"(class {name}\(Base\):[\s\S]+?)(?=\nclass |\Z)",
                text,
                re.MULTILINE,
            )
            return m.group(1) if m else None

        # 2️⃣ Thêm quan hệ cha → con
        block = find_block(parent)
        rel_marker = f"# 🧩 Auto relationship (parent → child): {child}"
        if block and rel_marker not in block:
            rel = (
                f"    {rel_marker}\n"
                f"    {child_field}: Mapped[Optional['{child}']] = relationship(\n"
                f"        '{child}', back_populates='{parent_field}', uselist=False)\n"
            )
            new_block = block.rstrip() + "\n" + rel + "\n"
            text = text.replace(block, new_block)
            added_relations.add((parent, child))

        # 3️⃣ Thêm quan hệ con → cha
        block = find_block(child)
        rel_marker = f"# 🧩 Auto relationship (child → parent): {parent}"
        if block and rel_marker not in block:
            rel = (
                f"    {rel_marker}\n"
                f"    {parent_field}: Mapped['{parent}'] = relationship(\n"
                f"        '{parent}', back_populates='{child_field}', uselist=False)\n"
            )
            new_block = block.rstrip() + "\n" + rel + "\n"
            text = text.replace(block, new_block)
            added_relations.add((child, parent))

    # ✅ Ghi chú tổng kết
    if "# === AUTO FIX SUMMARY ===" not in text:
        text += (
            "\n\n# === AUTO FIX SUMMARY ===\n"
            "# • Đã đổi class kế thừa (trừ Base) → Base.\n"
            "# • Đã thêm relationship() 1–1 hai chiều tự động (không trùng lặp).\n"
            "# • Field dùng snake_case (vd: lesson_videos, course_reviews, ...).\n"
            "# =========================\n"
        )

    Path(filepath).write_text(text, encoding="utf-8")
    print(f"✅ Đã fix kế thừa & thêm quan hệ 1–1 hai chiều: {filepath}")


if __name__ == "__main__":
    fix_sqlacodegen_file("app/db/models/database.py")
