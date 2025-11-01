import asyncio
import logging

import google.generativeai as genai
from google.api_core.exceptions import (
    InvalidArgument,
    PermissionDenied,
    ResourceExhausted,
)

from app.core.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Dịch vụ gọi Gemini LLM (ổn định, có fallback & retry)."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.GOOGLE_API_KEY_CHAT)
        self.primary_model = "gemini-2.5-flash"
        self.fallback_model = "gemini-1.5-flash"

    async def call_model(self, prompt: str, retries: int = 3) -> str:
        """
        Gọi mô hình Gemini để sinh nội dung.
        - Có retry tự động nếu gặp lỗi tạm thời (rate limit, quota).
        - Tự động fallback sang model nhẹ hơn nếu model chính lỗi nặng.
        """

        async def _safe_call(model_name: str) -> str:
            def _sync_call():
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)

                # Xử lý phản hồi không hợp lệ
                if not response or not getattr(response, "text", None):
                    return "⚠️ Mô hình không thể tạo phản hồi cho yêu cầu này."
                text = response.text.strip()
                # Kiểm tra độ rỗng / vô nghĩa
                if len(text) < 10 or "I’m sorry" in text or "Xin lỗi" in text:
                    return "⚠️ Mô hình không thể trả lời chính xác cho nội dung này."
                return text

            return await asyncio.to_thread(_sync_call)

        # ==== Gọi model chính kèm retry ====
        for attempt in range(1, retries + 1):
            try:
                return await _safe_call(self.primary_model)
            except ResourceExhausted:  # Quota exceeded / rate limit
                wait_time = 2 * attempt
                logger.warning(
                    f"⚠️ Quota bị giới hạn (attempt {attempt}/{retries}), đợi {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            except PermissionDenied:
                logger.error("🚫 API key không hợp lệ hoặc chưa bật billing.")
                return "🚫 API key không hợp lệ hoặc chưa bật billing cho dự án Google Cloud."
            except InvalidArgument as e:
                logger.error(f"❌ Lỗi tham số prompt: {e}")
                return "⚠️ Lỗi cú pháp prompt hoặc dữ liệu đầu vào không hợp lệ."
            except Exception as e:
                logger.warning(f"⚠️ Lỗi tạm khi gọi Gemini: {e}")
                await asyncio.sleep(2)

        # ==== Nếu model chính thất bại → thử fallback model ====
        try:
            logger.info("🔁 Đang thử gọi model dự phòng gemini-1.5-flash ...")
            return await _safe_call(self.fallback_model)
        except Exception as e:
            logger.error(f"❌ Cả 2 model Gemini đều thất bại: {e}")
            return "❌ Hệ thống tạm thời không thể tạo nội dung. Vui lòng thử lại sau."
