import uuid
from typing import Optional

from fastapi import Depends
from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService, get_embedding_service
from app.db.models.database import (
    Categories,
    CourseEnrollments,
    CourseReviews,
    Courses,
    LessonProgress,
    Lessons,
)
from app.db.sesson import get_session


class CourseEnrolls:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db
        self.embedding = embedding

    async def get_user_courses_async(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 10,
        keyword: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        level: Optional[str] = None,
        language: Optional[str] = None,
        sort_by: str = "enrolled_at",
        order: str = "desc",
    ):
        # ánh xạ field hợp lệ để tránh SQL injection
        valid_sort_fields = {
            "title": Courses.title,
            "rating_avg": Courses.rating_avg,
            "enrolled_at": CourseEnrollments.enrolled_at,
            "created_at": Courses.created_at,
            "views": Courses.views,
            "progress": func.coalesce(
                func.sum(case((LessonProgress.is_completed.is_(True), 1), else_=0))
                * 100
                / func.greatest(func.count(Lessons.id), 1),
                0,
            ),
        }

        sort_field = valid_sort_fields.get(sort_by, CourseEnrollments.enrolled_at)
        sort_order = desc if order.lower() == "desc" else asc

        # 🧮 Query chính
        query = (
            select(
                Courses.id,
                Courses.title,
                Courses.slug,
                Courses.thumbnail_url,
                Courses.rating_avg,
                Courses.total_length_seconds,
                Courses.level,
                Courses.language,
                Courses.created_at,
                CourseEnrollments.enrolled_at,
                Categories.name.label("category_name"),
                func.count(CourseReviews.id).label("review_count"),
                func.coalesce(func.avg(CourseReviews.rating), 0).label("avg_rating"),
                (
                    func.coalesce(
                        func.sum(
                            case(
                                (LessonProgress.is_completed.is_(True), 1),
                                else_=0,
                            )
                        ),
                        0,
                    )
                    * 100
                    / func.greatest(func.count(Lessons.id), 1)
                ).label("progress_percent"),
            )
            .join(CourseEnrollments, CourseEnrollments.course_id == Courses.id)
            .outerjoin(CourseReviews, CourseReviews.course_id == Courses.id)
            .outerjoin(Lessons, Lessons.course_id == Courses.id)
            .outerjoin(
                LessonProgress,
                (LessonProgress.course_id == Courses.id)
                & (LessonProgress.user_id == user_id)
                & (LessonProgress.lesson_id == Lessons.id),
            )
            .outerjoin(Categories, Categories.id == Courses.category_id)
            .where(CourseEnrollments.user_id == user_id)
            .group_by(
                Courses.id,
                Categories.name,
                CourseEnrollments.enrolled_at,
            )
        )

        # 🔍 Full-text + ILIKE fallback
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

        # 🎯 Lọc thêm
        if category_id:
            query = query.where(Courses.category_id == category_id)
        if level:
            query = query.where(Courses.level == level)
        if language:
            query = query.where(Courses.language == language)

        # 🧩 Sắp xếp
        query = query.order_by(sort_order(sort_field))
        query = query.offset((page - 1) * size).limit(size)

        # 📊 Tổng số bản ghi
        total_query = (
            select(func.count())
            .select_from(CourseEnrollments)
            .where(CourseEnrollments.user_id == user_id)
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
            "courses": data,
        }
