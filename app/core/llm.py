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
    """Dịch vụ gọi Gemini LLM (chuẩn API mới, ổn định, retry + fallback)."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.GOOGLE_API_KEY_CHAT)

        # === Model MỚI CHÍNH XÁC NHẤT CHO generate_content ===
        self.primary_model = "models/gemini-2.0-flash"
        self.fallback_model = "models/gemini-2.0-pro"

    async def call_model(
        self,
        prompt: str,
        retries: int = 3,
        mime_type: str = "application/json",
        temperature: float = 0.5,
        max_output_tokens: int = 8000,
    ) -> str:

        async def _safe_call(model_name: str) -> str:
            def _sync_call():
                model = genai.GenerativeModel(model_name)

                response = model.generate_content(
                    prompt,
                    generation_config={
                        "response_mime_type": mime_type,
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    },
                )

                # SDK mới: dùng .text không còn chắc chắn → dùng .candidates
                try:
                    text = response.text.strip()
                except Exception:
                    text = response.candidates[0].content.parts[0].text.strip()

                if not text:
                    return "⚠️ Mô hình không sinh được nội dung."

                return text

            return await asyncio.to_thread(_sync_call)

        # ===== Gọi model chính (retry) =====
        for attempt in range(1, retries + 1):
            try:
                return await _safe_call(self.primary_model)

            except ResourceExhausted:
                wait_time = 2 * attempt
                logger.warning(
                    f"⚠️ Quota bị giới hạn (attempt {attempt}/{retries}), đợi {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except PermissionDenied:
                logger.error("🚫 API key sai hoặc chưa bật billing.")
                return "🚫 API key không hợp lệ hoặc chưa bật billing."

            except InvalidArgument as e:
                logger.error(f"❌ Lỗi tham số: {e}")
                return "⚠️ Prompt không hợp lệ hoặc định dạng sai."

            except Exception as e:
                logger.warning(f"⚠️ Lỗi tạm thời từ Gemini: {e}")
                await asyncio.sleep(2)

        # ===== Fallback sang model mạnh hơn =====
        try:
            logger.info("🔁 Đang thử gọi model dự phòng (gemini-2.0-pro)...")
            return await _safe_call(self.fallback_model)

        except Exception as e:
            logger.error(f"❌ Fallback cũng fail: {e}")
            return "❌ Máy chủ AI đang quá tải, thử lại sau."
