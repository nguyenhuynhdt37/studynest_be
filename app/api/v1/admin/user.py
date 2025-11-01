import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.auth.user import BlockUser, EditUser
from app.services.admin.user import UserService

router = APIRouter(prefix="/admin/users", tags=["ADMIN USER"])


def get_user_service(user_service: UserService = Depends(UserService)) -> UserService:
    return user_service


def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


@router.get("")
async def get_users(
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
    search: str | None = Query(None, description="Tìm kiếm theo tên hoặc email"),
    is_verified_email: bool = Query(False),
    is_banned: bool = Query(False),
    sort_by: str = Query("create_at", description="Cột sắp xếp"),
    order: str = Query("desc", description="Hướng sắp xếp asc|desc"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
):
    await authorization.require_role(["ADMIN"])
    return await user_service.get_users_async(
        is_verified_email,
        is_banned,
        search,
        sort_by,
        order,
        page,
        size,
    )


@router.get("/deleted")
async def get_users_deleted(
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    is_verified_email: Optional[bool] = Query(None),
    order: str = Query("desc"),
    page: int = Query(1),
    size: int = Query(20),
):
    await authorization.require_role(["ADMIN"])
    return await user_service.get_users_deleted_async(
        search, is_verified_email, sort_by, order, page, size
    )


@router.put("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    schema: EditUser = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    admin = await authorization.require_role(["ADMIN"])
    return await user_service.update_user_async(schema, admin, user_id)


@router.get("/export")
async def export_user(
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    await authorization.require_role(["ADMIN"])
    return await user_service.export_user_async()


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    reason: str = Query(..., description="Lý do xoá người dùng"),
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    admin = await authorization.require_role(["ADMIN"])
    return await user_service.delete_user_async(admin, user_id, reason)


@router.get("/{user_id}")
async def get_user_by_id(
    user_id: uuid.UUID,
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    await authorization.require_role(["ADMIN"])
    return await user_service.get_user_by_id_async(user_id)


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: uuid.UUID,
    schema: BlockUser = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    admin = await authorization.require_role(["ADMIN"])
    return await user_service.ban_user_async(admin, user_id, schema)


@router.post("/{user_id}/unlock_ban")
async def unlock_ban_user(
    user_id: uuid.UUID,
    authorization: AuthorizationService = Depends(get_authorization_service),
    user_service: UserService = Depends(get_user_service),
):
    admin = await authorization.require_role(["ADMIN"])
    return await user_service.unlock_ban_user_async(admin, user_id)
    return await user_service.unlock_ban_user_async(admin, user_id)
