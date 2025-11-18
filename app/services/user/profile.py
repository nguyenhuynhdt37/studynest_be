import uuid

from fastapi import Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import User
from app.db.sesson import get_session
from app.schemas.user.profile import ProfileUpdate
from app.services.shares.google_driver import (
    GoogleDriveAsyncService,
    get_google_drive_service,
)


class ProfileService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive_service: GoogleDriveAsyncService = Depends(
            get_google_drive_service
        ),
    ):
        self.db = db
        self.google_drive_service = google_drive_service

    async def get_profile_by_user_id(self, user_id: uuid.UUID, is_me: bool = False):
        # Implementation to get user profile by user_id
        try:
            query = (
                select(
                    User.id,
                    User.fullname,
                    User.email,
                    User.avatar,
                    User.bio,
                    User.facebook_url,
                    is_me and User.birthday or None,
                    User.conscious,
                    is_me and User.district or None,
                    is_me and User.citizenship_identity or None,
                    User.last_login_at,
                    User.create_at.label("created_at"),
                    User.update_at.label("updated_at"),
                    User.is_banned,
                    User.banned_reason,
                    User.banned_until,
                )
                .where(User.id == user_id)
                .limit(1)
            )

            result = await self.db.execute(query)
            user = result.mappings().first()
            if not user:
                raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

            return user
        except Exception as e:

            raise HTTPException(status_code=500, detail=f"error {e}")

    async def upload_avatar_async(self, user_id: uuid.UUID, file: UploadFile):
        # Implementation to get user profile by user_id
        try:
            user = await self.db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

            file_url = await self.google_drive_service.upload_file(
                ["avatars", str(user_id)],
                file.filename or f"avatar_{user_id}_{uuid.uuid4()}.png",
                await file.read(),
                file.content_type,
            )
            user.avatar = file_url.get("webViewLink", None)
            await self.db.commit()
            return {
                "id": user.id,
                "avatar": user.avatar,
            }
        except Exception as e:

            raise HTTPException(status_code=500, detail=f"error {e}")

    async def update_profile_by_user_id(
        self, user_id: uuid.UUID, profile_data: ProfileUpdate
    ):
        user = await self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

        # cập nhật tự động theo field được gửi (tránh viết thủ công từng cái)
        for field, value in profile_data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        try:
            await self.db.commit()
            await self.db.refresh(user)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật hồ sơ: {e}")

        return {
            "id": str(user.id),
            "fullname": user.fullname,
            "bio": user.bio,
            "facebook_url": user.facebook_url,
            "birthday": user.birthday,
            "conscious": user.conscious,
            "district": user.district,
            "citizenship_identity": user.citizenship_identity,
        }
