# app/core/embedding.py
import asyncio
import mimetypes
import uuid
from datetime import datetime
from math import exp

import google.generativeai as genai
import numpy as np
import tiktoken
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMService
from app.core.settings import settings
from app.db.models.database import User, UserEmbeddingHistory
from app.db.sesson import AsyncSessionLocal


class EmbeddingService:
    EMBED_MODEL = "models/gemini-embedding-001"
    EMBED_DIM = 3072

    def __init__(self, llm_service: LLMService = Depends(LLMService)):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.llm_service = llm_service
        self._enc = tiktoken.get_encoding("cl100k_base")

    # ========== EMBEDDING ==========
    async def embed_google_3072(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.EMBED_DIM

        def _sync_embed():
            resp = genai.embed_content(
                model=self.EMBED_MODEL,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=self.EMBED_DIM,
            )
            return resp["embedding"]

        return await asyncio.to_thread(_sync_embed)

    # ========== GEMINI 2.5 FLASH ==========

    async def extract_video_context_from_url(self, url_sharelink: str) -> str:
        prompt = f"""
        Bạn là **trợ lý AI chuyên phân tích video học tập**, được thiết kế để tối ưu hóa dữ liệu cho hệ thống RAG (Retrieval-Augmented Generation).

        Hãy xem video tại liên kết sau và xuất ra **bản tóm tắt chi tiết dưới dạng Markdown**, với cấu trúc rõ ràng, dễ lập chỉ mục (index) và dễ tách đoạn cho embedding.

        ## Yêu cầu xuất kết quả
        - Ghi rõ **mốc thời gian (hh:mm:ss)** cho từng đoạn quan trọng (ví dụ: `0:45 - Giải thích khái niệm Measure`).
        - Liệt kê **tên chương hoặc nội dung chính**.
        - Trình bày **các ý quan trọng theo thứ tự thời gian**.
        - Mô tả **hành động hoặc kiến thức cốt lõi** mà giảng viên truyền đạt.
        - Nêu **chủ đề chính** và **mục tiêu khóa học**.
        - Tóm tắt **các kiến thức hoặc kỹ năng được truyền đạt**, bao gồm cả thuật ngữ kỹ thuật và ví dụ minh họa.
        - Xác định **đối tượng học phù hợp** (người mới, trung cấp, nâng cao).
        - Mô tả **cấu trúc video** (phần mở đầu, lý thuyết, demo, thực hành, tổng kết) nếu có thể suy luận.
        - Ngôn ngữ đầu ra giữ nguyên **ngôn ngữ gốc của video** (ví dụ: video tiếng Việt → kết quả tiếng Việt).

        ## Mục tiêu xử lý
        - Giúp hệ thống RAG có thể truy xuất chính xác nội dung theo mốc thời gian.
        - Đảm bảo mỗi đoạn nội dung có **ngữ cảnh độc lập** và đủ chi tiết để sinh embedding vector hiệu quả.
        - Tránh văn phong quảng cáo hay diễn giải lan man — chỉ tập trung vào **nội dung giảng dạy và kiến thức học tập.**

        ## Giới hạn đầu ra
        - Nếu video dài, chỉ mô tả chi tiết **phần đầu tiên (tối đa 15 phút)**.
        - Nếu không truy cập được video, hãy **tạo bản mô tả dựa trên metadata, tiêu đề, hoặc nội dung có thể suy luận.**

        Video: {url_sharelink}
        """
        return await self.llm_service.call_model(prompt)

    # ========== TOKENIZER ==========
    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            return len(self._enc.encode(text))
        except Exception:
            return len(text.split())

    def guess_mime_type(self, url: str) -> str:
        mime, _ = mimetypes.guess_type(url)
        return mime or "video/mp4"

    def split_text_by_tokens(self, text: str, max_tokens: int = 1000):
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        chunks = []
        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i : i + max_tokens]
            chunk_text = enc.decode(chunk_tokens)
            chunks.append(chunk_text)
        return chunks

    # ========== ADAPTIVE USER EMBEDDING ==========
    async def update_user_embedding_adaptive(
        self,
        user_id: uuid.UUID,
        new_embedding: list[float] | None,
        interaction_type: str = "wishlist",
        course_id: uuid.UUID | None = None,
    ):
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            if not user:
                return

            # Nếu bỏ yêu thích → tính lại
            if new_embedding is None:
                updated_vector = await self.recompute_user_embedding(
                    db, user_id, exclude_course_id=course_id
                )
                user.preferences_embedding = updated_vector
                user.preferences_embedding_date_updated_at = datetime.utcnow()
                return

            strength = {
                "wishlist": 0.5,
                "start": 0.7,
                "complete": 1.0,
                "review": 1.2,
            }.get(interaction_type, 0.6)

            if (
                user.preferences_embedding is None
                or len(user.preferences_embedding) == 0
            ):
                old_vec = np.zeros(3072)
            else:
                old_vec = np.array(user.preferences_embedding)

            new_vec = np.array(new_embedding)
            days_since = (
                datetime.utcnow()
                - (user.preferences_embedding_date_updated_at or datetime.utcnow())
            ).days

            sim = np.dot(old_vec, new_vec) / (
                np.linalg.norm(old_vec) * np.linalg.norm(new_vec) + 1e-9
            )
            sim = np.clip(sim, 0.0, 1.0)

            base_lambda = 0.004
            lambda_ = (
                base_lambda * (1 + min(days_since / 60, 2.0) + (1 - sim) * 2) * strength
            )

            decay = exp(-lambda_ * days_since)
            updated = (old_vec * decay + new_vec) / (1 + decay)

            user.preferences_embedding = updated.tolist()
            user.preferences_embedding_date_updated_at = datetime.utcnow()

            db.add(
                UserEmbeddingHistory(
                    user_id=user_id,
                    course_id=course_id,
                    embedding=new_embedding,
                    interaction_type=interaction_type,
                    lambda_=lambda_,
                    similarity=sim,
                    decay=decay,
                )
            )

            print(
                f"[Embedding ✅] user={user.id} | type={interaction_type} | λ={lambda_:.5f} | sim={sim:.2f}"
            )
            await db.commit()

    async def recompute_user_embedding(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        exclude_course_id: uuid.UUID | None = None,
    ) -> list[float]:
        result = await db.scalars(
            select(UserEmbeddingHistory)
            .where(UserEmbeddingHistory.user_id == user_id)
            .order_by(UserEmbeddingHistory.created_at.asc())
        )
        history = result.all()

        if not history:
            return np.zeros(3072).tolist()

        vec = np.zeros(3072)
        last_time = history[0].created_at

        for h in history:
            if (
                exclude_course_id
                and h.course_id == exclude_course_id
                and h.interaction_type == "wishlist"
            ):
                continue

            days = (h.created_at - last_time).days
            decay = exp(-h.lambda_ * days)
            vec = (vec * decay + np.array(h.embedding)) / (1 + decay)
            last_time = h.created_at

        return vec.tolist()
