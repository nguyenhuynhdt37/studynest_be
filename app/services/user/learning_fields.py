# app/services/learning_field_service.py
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService
from app.db.models.database import LearningFields, User
from app.db.sesson import get_session
from app.schemas.user.learning_fields import LearningFielsSave


class LearningFieldService:
    """Service quản lý lĩnh vực học tập (Learning Fields) và sở thích người dùng."""

    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(EmbeddingService),
    ):
        self.db = db
        self.embedding = embedding

    async def get_learning_fields_async(self) -> List[Dict[str, Any]]:
        """Lấy danh sách lĩnh vực học tập, xây cây phân cấp (tree structure)."""
        try:
            learning_fields = (await self.db.scalars(select(LearningFields))).all()

            # Gom nhóm theo parent_id
            by_parent: Dict[Optional[uuid.UUID], List[LearningFields]] = {}
            for f in learning_fields:
                by_parent.setdefault(f.parent_id, []).append(f)

            # Đệ quy xây cây
            def build_tree(
                parent_id: Optional[uuid.UUID] = None,
            ) -> List[Dict[str, Any]]:
                return [
                    {
                        "id": field.id,
                        "name": field.name,
                        "description": field.description,
                        "parent_id": field.parent_id,
                        "children": build_tree(field.id),
                    }
                    for field in sorted(
                        by_parent.get(parent_id, []), key=lambda x: x.id
                    )
                ]

            return build_tree(None)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy lĩnh vực học tập: {e}")

    async def save_user_learning_preferences_async(
        self, schema: LearningFielsSave, user: User
    ) -> dict[str, Any]:
        """
        Lưu embedding cho sở thích học tập người dùng:
        - Sinh embedding Google 3072 từ nội dung văn bản
        - Lưu vector vào cột preferences_embedding
        """
        try:
            # 1️⃣ Sinh embedding
            vec = await self.embedding.embed_google_3072(schema.preferences)

            # 2️⃣ Cập nhật thông tin user
            user.preferences_embedding = vec
            user.preferences_str = schema.preferences
            user.preferences_embedding_date_updated_at = datetime.utcnow()

            await self.db.commit()
            return {
                "message": "Đã lưu sở thích học tập",
                "updated_at": user.preferences_embedding_date_updated_at,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lưu sở thích học tập: {e}")
