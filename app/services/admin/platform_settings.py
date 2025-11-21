import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import PlatformSettings
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now


class PlatformSettingsService:
    """
    Singleton service chứa cache.
    Nhưng db session được update mỗi request.
    """

    def __init__(self):
        self.db: AsyncSession  # session sẽ được gán bởi dependency
        self.cache = None
        self.expire = None

    async def get(self):
        try:
            now = get_now()

            if self.cache and self.expire and self.expire > now:
                return self.cache

            row = await self.db.scalar(select(PlatformSettings))
            if not row:
                raise HTTPException(500, "Platform settings missing")

            self.cache = row
            self.expire = now + timedelta(minutes=5)
            return row

        except Exception as e:
            raise HTTPException(500, f"Error loading platform settings: {e}")

    async def update(self, body, admin_id: uuid.UUID):
        try:
            row = await self.db.scalar(select(PlatformSettings))

            if not row:
                raise HTTPException(500, "Platform settings missing")

            for field, value in body.dict(exclude_unset=True).items():
                setattr(row, field, value)

            row.updated_by = admin_id
            row.updated_at = get_now()

            await self.db.flush()

            self.cache = row
            self.expire = get_now() + timedelta(minutes=5)

            return row

        except Exception as e:
            raise HTTPException(500, f"Error updating settings: {e}")


# ========= Singleton dependency =========

_singleton_service: Optional[PlatformSettingsService] = None


async def get_platform_settings_service(
    db: AsyncSession = Depends(get_session),
) -> PlatformSettingsService:
    """
    Singleton instance + inject db session mới mỗi request.
    """
    global _singleton_service

    if _singleton_service is None:
        logger.info("🚀 Khởi tạo PlatformSettingsService lần đầu.")
        _singleton_service = PlatformSettingsService()

    # Gán session mới cho service mỗi request
    _singleton_service.db = db

    return _singleton_service
