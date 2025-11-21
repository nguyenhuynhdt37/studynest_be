from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService
from app.db.models.database import User
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.schemas.user.learning_fields import LearningFielsSave


class UserPreferencesService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(EmbeddingService),
    ):
        self.db = db
        self.embedding = embedding

    async def save_user_learning_preferences_async(
        self, schema: LearningFielsSave, user: User
    ) -> dict[str, Any]:

        try:
            # 1️⃣ Sinh embedding
            vec = await self.embedding.embed_google_normalized(schema.preferences)

            # 2️⃣ Cập nhật thông tin user
            user.preferences_embedding = vec
            user.preferences_str = schema.preferences
            user.preferences_embedding_date_updated_at = get_now()

            await self.db.commit()
            return {
                "message": "Đã lưu sở thích học tập",
                "updated_at": user.preferences_embedding_date_updated_at,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lưu sở thích học tập: {e}")
