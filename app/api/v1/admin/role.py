# app/api/v1/admin/role_router.py
import uuid

from fastapi import APIRouter, Body, Depends, Query

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.admin.role import CreateRole, UpadteRole
from app.services.admin.role import RoleService

router = APIRouter(prefix="/admin/roles", tags=["ADMIN ROLES"])


# ✅ Inject RoleService chuẩn
def get_role_service(role_service: RoleService = Depends(RoleService)) -> RoleService:
    return role_service


# ✅ Inject RoleService chuẩn
def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


# ---------------- ROUTES ----------------
@router.get("")
async def get_roles(
    search: str | None = Query(None, description="Tìm kiếm theo tên"),
    sort_by: str = Query("role_name"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    service: RoleService = Depends(get_role_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_roles_async(search, sort_by, order, page, size)


@router.post("", status_code=201)
async def create_role(
    schema: CreateRole = Body(...),
    service: RoleService = Depends(get_role_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.create_role_async(schema)


@router.delete("/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    service: RoleService = Depends(get_role_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.delete_role_async(role_id)


@router.put("/{role_id}", status_code=204)
async def update_role(
    role_id: uuid.UUID,
    schema: UpadteRole = Body(...),
    service: RoleService = Depends(get_role_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.update_role_async(role_id, schema)
