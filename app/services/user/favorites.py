# app/services/course_favorite_service.py
import uuid

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService
from app.db.models.database import CourseFavourites, Courses, User
from app.db.sesson import get_session


class CourseFavoriteService:
    """Service xử lý logic yêu thích (favourite/wishlist) khóa học."""

    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(EmbeddingService),
    ):
        self.db = db
        self.embedding = embedding

    async def toggle_favorite_course_async(
        self,
        course_id: uuid.UUID,
        background_tasks: BackgroundTasks,
        user: User,
    ):
        try:
            # 1️⃣ Lấy khóa học
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            # 2️⃣ Kiểm tra đã yêu thích chưa
            favorite = await self.db.scalar(
                select(CourseFavourites)
                .where(CourseFavourites.course_id == course_id)
                .where(CourseFavourites.user_id == user.id)
            )

            if favorite:
                # 🧹 Nếu đã thích → Xóa + cập nhật lại embedding người dùng
                await self.db.delete(favorite)
                await self.db.commit()

                background_tasks.add_task(
                    self.embedding.update_user_embedding_adaptive,
                    user.id,
                    None,
                    "wishlist",
                    course_id,
                )

                return {"message": "Đã bỏ thích khóa học", "is_favourite": False}

            else:
                # ❤️ Nếu chưa thích → Thêm mới + cập nhật embedding
                self.db.add(CourseFavourites(user_id=user.id, course_id=course_id))
                await self.db.commit()

                if course.embedding is not None:
                    background_tasks.add_task(
                        self.embedding.update_user_embedding_adaptive,
                        user.id,
                        course.embedding,
                        "wishlist",
                        course_id,
                    )

                return {"message": "Đã yêu thích khóa học", "is_favourite": True}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi toggle yêu thích khóa học: {e}")

    async def check_is_favorite_course_async(self, course_id: uuid.UUID, user: User):
        """Kiểm tra người dùng có đang yêu thích khóa học không"""
        try:
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            favorite = await self.db.scalar(
                select(CourseFavourites).where(
                    CourseFavourites.course_id == course_id,
                    CourseFavourites.user_id == user.id,
                )
            )

            return {
                "is_favourite": favorite is not None,
                "message": (
                    "Người dùng đang yêu thích khóa học này"
                    if favorite
                    else "Người dùng chưa yêu thích khóa học này"
                ),
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi khi kiểm tra yêu thích: {e}")
