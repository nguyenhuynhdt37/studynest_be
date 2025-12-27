# app/services/category_service.py


import datetime
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import (
    TEXT,
    UUID,
    and_,
    asc,
    cast,
    func,
    literal,
    literal_column,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db.models.database import Categories, Courses, User
from app.db.sesson import get_session


class CategoryService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_categories_async(self, limit_parent: int = 10, limit_child: int = 15):
        try:
            stmt = (
                select(Categories)
                .options(selectinload(Categories.parent_reverse))
                .where(Categories.parent_id.is_(None))
                .order_by(Categories.order_index)
                .limit(limit_parent)
            )
            result = await self.db.scalars(stmt)
            categories = result.unique().all()

            # sắp xếp và giới hạn con
            for cat in categories:
                cat.parent_reverse.sort(key=lambda x: x.order_index)
                cat.parent_reverse = cat.parent_reverse[:limit_child]

            return categories

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy danh mục: {e}")

    async def get_all_categories_async(self):
        query = select(
            Categories.id,
            Categories.name,
            Categories.slug,
        ).order_by(asc(Categories.name))

        result = await self.db.execute(query)
        data = result.mappings().all()
        return data

    async def get_all_subcategories(self, category_slug: str):
        try:
            category: Categories | None = await self.db.scalar(
                select(Categories).where(Categories.slug == category_slug)
            )
            if category is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
            category_id = category.id
            query = text("SELECT * FROM fn_get_category_tree(:cid)")
            rows = await self.db.execute(query, {"cid": str(category_id)})
            return [r[0] for r in rows.all()]
        except Exception as e:
            raise e

    async def get_categories_with_topics(self):
        try:

            stmt = (
                select(Categories)
                .options(selectinload(Categories.topics))
                .order_by(Categories.order_index.asc(), Categories.name.asc())
            )

            rows = (await self.db.execute(stmt)).scalars().all()

            return [
                {
                    "id": str(cat.id),
                    "name": cat.name,
                    "slug": cat.slug,
                    "parent_id": str(cat.parent_id) if cat.parent_id else None,
                    "topics": [
                        {"id": str(t.id), "name": t.name, "slug": t.slug}
                        for t in cat.topics
                    ],
                }
                for cat in rows
            ]

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy danh mục với chủ đề: {e}")

    # hàm lấy những danh mục liên quan
    async def get_related_categories(self, slug: str):
        try:
            stmt = select(
                literal_column("id"),
                literal_column("name"),
                literal_column("slug"),
                literal_column("parent_id"),
                literal_column("total_courses"),
            ).select_from(func.fn_get_related_categories_by_slug(slug))

            rows = (await self.db.execute(stmt)).mappings().all()

            return [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "slug": r["slug"],
                    "parent_id": str(r["parent_id"]) if r["parent_id"] else None,
                    "total_courses": int(r["total_courses"]),
                }
                for r in rows
            ]

        except Exception as e:
            print("❌ Category related function error:", e)
            raise e

    async def get_related_courses_async(self, user_id: uuid.UUID, category_slug: str):
        try:
            category = await self.db.scalar(
                select(Categories).where(Categories.slug == category_slug)
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Category not found",
                )

            stmt = select(
                literal_column("course_id"),
                literal_column("course_title"),
                literal_column("course_thumbnail"),
                literal_column("instructor_id"),
                literal_column("instructor_name"),
                literal_column("instructor_avatar"),
                literal_column("views"),
                literal_column("enrolls"),
                literal_column("rating"),
                literal_column("score"),
            ).select_from(
                func.fn_related_courses(
                    cast(literal(str(user_id)), UUID),  # ⬅ FIX CHUẨN
                    cast(literal(str(category.id)), UUID),  # ⬅ FIX CHUẨN
                )
            )

            rows = (await self.db.execute(stmt)).mappings().all()

            return {
                "items": [
                    {
                        "id": str(r["course_id"]),
                        "title": r["course_title"],
                        "thumbnail": r["course_thumbnail"],
                        "instructor": {
                            "id": str(r["instructor_id"]),
                            "name": r["instructor_name"],
                            "avatar": r["instructor_avatar"],
                        },
                        "views": r["views"],
                        "enrolls": r["enrolls"],
                        "rating": float(r["rating"]),
                        "score": float(r["score"]),
                    }
                    for r in rows
                ]
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi related courses: {e}")

    async def get_top_instructors(self, category_slug: str):
        # 2) Lấy subtree categories
        category_ids = await self.get_all_subcategories(category_slug)

        # 3) SELECT group by instructor
        stmt = (
            select(
                Courses.instructor_id,
                func.count(Courses.id).label("total_courses"),
                func.sum(func.coalesce(Courses.total_enrolls, 0)).label(
                    "total_enrolls"
                ),
                User.fullname,
                User.avatar,
            )
            .join(User, User.id == Courses.instructor_id)
            .where(
                Courses.category_id.in_(category_ids),
                Courses.is_published.is_(True),
                Courses.approval_status == "approved",
            )
            .group_by(Courses.instructor_id, User.fullname, User.avatar)
            .order_by(func.sum(func.coalesce(Courses.total_enrolls, 0)).desc())
            .limit(20)
        )

        rows = (await self.db.execute(stmt)).mappings().all()

        return {
            "items": [
                {
                    "instructor_id": str(r["instructor_id"]),
                    "instructor_name": r["fullname"],
                    "instructor_avatar": r["avatar"],
                    "total_courses": r["total_courses"],
                    "total_enrolls": r["total_enrolls"],
                }
                for r in rows
            ]
        }

    async def get_category_courses(
        self,
        category_slug: str,
        limit: int = 20,
        cursor: Optional[str] = None,
        rating: Optional[float] = None,
        duration: Optional[str] = None,
        level: Optional[str] = None,
        language: Optional[str] = None,
        sort: str = "newest",
    ):
        try:
            # 2) Lấy subtree categories
            category_ids = await self.get_all_subcategories(category_slug)

            Instructor = aliased(User)

            # 3) Base query
            stmt = (
                select(
                    Courses.id,
                    Courses.title,
                    Courses.slug,
                    Courses.thumbnail_url,
                    Courses.rating_avg,
                    Courses.rating_count,
                    Courses.total_length_seconds,
                    Courses.level,
                    Courses.language,
                    Courses.created_at,
                    Instructor.id.label("instructor_id"),
                    Instructor.fullname.label("instructor_name"),
                    Instructor.avatar.label("instructor_avatar"),
                )
                .join(Instructor, Instructor.id == Courses.instructor_id)
                .where(Courses.category_id.in_(category_ids))
            )

            # 4) FILTERS
            if rating:
                stmt = stmt.where(Courses.rating_avg >= rating)

            # duration filter → chuyển sang filter theo seconds
            if duration:
                ranges = {
                    "0-1": (0, 3600),
                    "1-3": (3600, 10800),
                    "3-6": (10800, 21600),
                    "6-17": (21600, 61200),
                }
                if duration in ranges:
                    low, high = ranges[duration]
                    stmt = stmt.where(
                        and_(
                            Courses.total_length_seconds >= low,
                            Courses.total_length_seconds <= high,
                        )
                    )

            if level:
                stmt = stmt.where(Courses.level == level)

            if language:
                stmt = stmt.where(Courses.language == language)

            # 5) SORT + CURSOR
            if sort == "newest":
                sort_field = Courses.created_at
            elif sort == "top_rated":
                sort_field = Courses.rating_avg
            else:
                sort_field = Courses.created_at

            stmt = stmt.order_by(sort_field.desc())

            # cursor
            if cursor:
                if sort == "newest":
                    cursor_val = datetime.datetime.fromisoformat(cursor)
                    stmt = stmt.where(Courses.created_at < cursor_val)
                elif sort == "top_rated":
                    cursor_val = float(cursor)
                    stmt = stmt.where(Courses.rating_avg < cursor_val)

            stmt = stmt.limit(limit + 1)

            # 6) Query
            rows = (await self.db.execute(stmt)).all()

            has_more = len(rows) > limit
            items = rows[:limit]

            if has_more:
                last = items[-1]
                if sort == "newest":
                    next_cursor = last.created_at.isoformat()
                else:
                    next_cursor = str(last.rating_avg)
            else:
                next_cursor = None

            # 7) Format output
            results = []
            for r in items:
                total_hours = (r.total_length_seconds or 0) / 3600

                results.append(
                    {
                        "id": r.id,
                        "title": r.title,
                        "slug": r.slug,
                        "thumbnail": r.thumbnail_url,
                        "rating_avg": float(r.rating_avg or 0),
                        "rating_count": r.rating_count,
                        "total_hours": round(total_hours, 1),
                        "level": r.level,
                        "language": r.language,
                        "created_at": r.created_at.isoformat(),
                        "instructor": {
                            "id": r.instructor_id,
                            "fullname": r.instructor_name,
                            "avatar": r.instructor_avatar,
                        },
                    }
                )

            return {
                "items": results,
                "next_cursor": next_cursor,
                "has_more": has_more,
            }

        except Exception as e:
            print("❌ Category courses error:", e)
            raise HTTPException(
                500, f"Lỗi khi lấy danh sách khóa học theo category. {e}"
            )

    async def get_root_and_level1_async(self, slug: str):
        try:
            stmt = select(
                literal_column("id"),
                literal_column("name"),
                literal_column("slug"),
                literal_column("level"),
            ).select_from(
                func.fn_get_root_and_level1_from_slug(
                    cast(literal_column(f"'{slug}'"), TEXT)
                )
            )

            rows = (await self.db.execute(stmt)).mappings().all()

            return {
                "items": [
                    {
                        "id": str(r["id"]),
                        "name": r["name"],
                        "slug": r["slug"],
                        "level": int(r["level"]),
                    }
                    for r in rows
                ]
            }

        except Exception as e:
            await self.db.rollback()
            raise e
