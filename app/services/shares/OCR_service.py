from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import List, Union, cast

import easyocr
import fitz  # PyMuPDF
import httpx
from loguru import logger
from PIL import Image


class OCRService:
    """
    Dịch vụ OCR: trích xuất văn bản từ PDF hoặc ảnh.
    - Hoạt động hoàn toàn trong RAM (không ghi ra đĩa).
    - EasyOCR chỉ được load 1 lần (singleton).
    """

    def __init__(self):
        logger.info("⚙️ Khởi tạo EasyOCR reader (vi)...")
        self.reader = easyocr.Reader(["vi"], gpu=False)

    # ============================================================
    # 📄 OCR PDF
    # ============================================================
    def extract_text_from_pdf(self, source: Union[str, Path, bytes]) -> str:
        try:
            pdf_bytes = self._load_pdf_bytes(source)
            pdf_stream = BytesIO(pdf_bytes)
            results: List[str] = []

            with fitz.open(stream=pdf_stream, filetype="pdf") as doc:
                total_pages = len(doc)
                logger.info(f"📄 OCR {total_pages} trang PDF (RAM-only)...")

                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes(
                        "RGBA" if pix.alpha else "RGB",
                        (pix.width, pix.height),
                        pix.samples,
                    )

                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)

                    text_blocks = cast(
                        List[str],
                        self.reader.readtext(buf.getvalue(), detail=0, paragraph=True),
                    )
                    page_text = "\n".join(text_blocks).strip()
                    if page_text:
                        results.append(page_text)
                        logger.info(
                            f"✅ Trang {i+1}/{total_pages}: {len(page_text)} ký tự"
                        )

            if not results:
                raise RuntimeError("❌ Không trích xuất được nội dung PDF.")
            return "\n\n".join(results)

        except Exception as e:
            logger.exception(f"❌ Lỗi OCR PDF: {e}")
            raise RuntimeError(f"Lỗi OCR PDF: {e}") from e

    async def _detect_type(self, content_type: str) -> str:
        """
        Hàm xác định loại tài nguyên (resource_type) dựa trên content_type của file.

        Args:
            content_type (str): MIME type của file (vd: 'application/pdf', 'image/png', 'text/plain')

        Returns:
            str: Loại tài nguyên ('pdf', 'image', 'text', 'unknown')
        """
        if not content_type:
            return "unknown"

        if "pdf" in content_type:
            return "pdf"
        elif "image" in content_type:
            return "image"
        elif "text" in content_type or "plain" in content_type:
            return "text"
        elif "json" in content_type:
            return "json"
        elif "video" in content_type:
            return "video"
        elif "audio" in content_type:
            return "audio"
        else:
            return "unknown"

    # ============================================================
    # 🖼️ OCR ẢNH
    # ============================================================
    def extract_text_from_image(self, source: Union[str, Path, bytes]) -> str:
        try:
            image_bytes = self._load_image_bytes(source)
            logger.info("🖼️ Đang OCR ảnh từ RAM...")

            text_blocks = cast(
                List[str],
                self.reader.readtext(image_bytes, detail=0, paragraph=True),
            )
            text = "\n".join(text_blocks).strip()
            if not text:
                raise RuntimeError("❌ Không trích xuất được text từ ảnh.")
            return text

        except Exception as e:
            logger.exception(f"❌ Lỗi OCR ảnh: {e}")
            raise RuntimeError(f"Lỗi OCR ảnh: {e}") from e

    # ============================================================
    # 🔧 Helper: Load dữ liệu
    # ============================================================
    def _load_pdf_bytes(self, source: Union[str, Path, bytes]) -> bytes:
        if isinstance(source, bytes):
            return source
        if isinstance(source, str) and re.match(r"^https?://", source):
            logger.info(f"🌐 Tải PDF từ URL: {source}")
            with httpx.stream("GET", source, timeout=60.0) as resp:
                resp.raise_for_status()
                return b"".join(resp.iter_bytes())
        pdf_path = Path(source)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")
        return pdf_path.read_bytes()

    def _load_image_bytes(self, source: Union[str, Path, bytes]) -> bytes:
        if isinstance(source, bytes):
            return source
        if isinstance(source, str) and re.match(r"^https?://", source):
            with httpx.stream("GET", source, timeout=30.0) as resp:
                resp.raise_for_status()
                return b"".join(resp.iter_bytes())
        img_path = Path(source)
        if not img_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file ảnh: {img_path}")
        return img_path.read_bytes()


# ============================================================
# ⚡ Singleton Provider cho FastAPI
# ============================================================
_ocr_service_instance = None


def get_ocr_service() -> OCRService:
    global _ocr_service_instance
    """
    Singleton OCRService — chỉ khởi tạo 1 lần duy nhất trong suốt vòng đời app.
    Dùng cho FastAPI: ocr_service: OCRService = Depends(get_ocr_service)
    """
    if _ocr_service_instance is None:
        logger.info("🚀 Tạo OCRService singleton (lần đầu tiên)")
        _ocr_service_instance = OCRService()
    return _ocr_service_instance
