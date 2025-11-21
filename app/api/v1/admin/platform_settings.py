from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.schemas.admin.platform_settings import UpdateSettingsSchema
from app.services.admin.platform_settings import (
    PlatformSettingsService,
    get_platform_settings_service,
)

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


@router.get("", status_code=200)
async def get_settings(
    service: PlatformSettingsService = Depends(get_platform_settings_service),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    await authorization.require_role(["ADMIN"])
    return await service.get()


@router.put("")
async def update_settings(
    body: UpdateSettingsSchema,
    authorization=Depends(AuthorizationService),
    service=Depends(get_platform_settings_service),
):
    admin = await authorization.require_role(["ADMIN"])
    return await service.update(body, admin.id)
