# app/services/category_service.py
from fastapi import Depends, HTTPException
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.database import Categories
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
