from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.deps import AuthorizationService
from app.schemas.user.profile import ProfileUpdate
from app.services.shares.profile import ProfileService

router = APIRouter(prefix="/profile", tags=["User Profile"])


@router.get("", status_code=status.HTTP_200_OK)
async def get_profile_by_user(
    profile_service: ProfileService = Depends(ProfileService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization_service.get_current_user()
    return await profile_service.get_profile_by_user_id(user.id, True)


@router.put("", status_code=status.HTTP_200_OK)
async def update_profile_by_user(
    profile_data: ProfileUpdate,
    profile_service: ProfileService = Depends(ProfileService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization_service.get_current_user()
    return await profile_service.update_profile_by_user_id(user.id, profile_data)


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def getCategory_all(
    user_id: UUID,
    profile_service: ProfileService = Depends(ProfileService),
):
    return await profile_service.get_profile_by_user_id(user_id)


@router.put("/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar_async(
    file: UploadFile = File(...),
    profile_service: ProfileService = Depends(ProfileService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization_service.get_current_user()
    return await profile_service.upload_avatar_async(user.id, file)
