# app/services/course_favorite_service.py
import uuid
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import asc, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService
from app.db.models.database import (
    Categories,
    CourseEnrollments,
    CourseFavourites,
    CourseReviews,
    Courses,
    User,
)
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

    async def get_user_favourite_courses_async(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 10,
        keyword: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        level: Optional[str] = None,
        language: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ):
        """
        Lấy danh sách khóa học yêu thích của user.
        Nếu user đã mua khóa học (có enroll) thì xóa khỏi favourites trước khi trả về.
        """

        # 🔹 Xóa các khóa học đã mua khỏi danh sách yêu thích
        sub_enrolled = (
            select(CourseEnrollments.course_id)
            .where(CourseEnrollments.user_id == user_id)
            .subquery()
        )
        delete_query = delete(CourseFavourites).where(
            CourseFavourites.user_id == user_id,
            CourseFavourites.course_id.in_(select(sub_enrolled.c.course_id)),
        )
        await self.db.execute(delete_query)
        await self.db.commit()

        # 🔹 Ánh xạ field sắp xếp hợp lệ
        valid_sort_fields = {
            "title": Courses.title,
            "rating_avg": Courses.rating_avg,
            "created_at": Courses.created_at,
            "views": Courses.views,
        }
        sort_field = valid_sort_fields.get(sort_by, Courses.created_at)
        sort_order = desc if order.lower() == "desc" else asc

        # 🔹 Truy vấn danh sách yêu thích còn lại
        query = (
            select(
                Courses.id,
                Courses.title,
                Courses.slug,
                Courses.thumbnail_url,
                Courses.rating_avg,
                Courses.level,
                Courses.language,
                Courses.created_at,
                Categories.name.label("category_name"),
                func.count(CourseReviews.id).label("review_count"),
                func.coalesce(func.avg(CourseReviews.rating), 0).label("avg_rating"),
                CourseFavourites.created_at.label("favourited_at"),
            )
            .join(CourseFavourites, CourseFavourites.course_id == Courses.id)
            .outerjoin(Categories, Categories.id == Courses.category_id)
            .outerjoin(CourseReviews, CourseReviews.course_id == Courses.id)
            .where(CourseFavourites.user_id == user_id)
            .group_by(Courses.id, Categories.name, CourseFavourites.created_at)
        )

        # 🔍 Lọc theo từ khóa
        if keyword:
            kw = f"%{keyword.lower()}%"
            query = query.where(
                or_(
                    func.lower(Courses.title).ilike(kw),
                    func.lower(Courses.description).ilike(kw),
                    Courses.search_tsv.op("@@")(
                        func.plainto_tsquery("simple", keyword)
                    ),
                )
            )

        # 🎯 Lọc nâng cao
        if category_id:
            query = query.where(Courses.category_id == category_id)
        if level:
            query = query.where(Courses.level == level)
        if language:
            query = query.where(Courses.language == language)

        # ⚡ Sắp xếp & phân trang
        query = query.order_by(sort_order(sort_field))
        query = query.offset((page - 1) * size).limit(size)

        # 📊 Tổng số
        total_query = (
            select(func.count())
            .select_from(CourseFavourites)
            .where(CourseFavourites.user_id == user_id)
        )

        result = await self.db.execute(query)
        total = await self.db.scalar(total_query)
        data = result.mappings().all()

        return {
            "page": page,
            "size": size,
            "total": total,
            "filters": {
                "keyword": keyword,
                "category_id": category_id,
                "level": level,
                "language": language,
                "sort_by": sort_by,
                "order": order,
            },
            "favourites": data,
        }
