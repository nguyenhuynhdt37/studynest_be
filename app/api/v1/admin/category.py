import uuid

from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.admin.category import CreateCategory, UpdateCategory
from app.services.admin.category import CategoryService

router = APIRouter(prefix="/admin/categories", tags=["ADMIN CATEGORIES"])


# ✅ Inject CategoryService chuẩn
def get_category_service(
    category_service: CategoryService = Depends(CategoryService),
) -> CategoryService:
    return category_service


# ✅ Inject RoleService chuẩn
def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


# ---------------- ROUTES ----------------
@router.get("")
async def get_categories_flat(
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    parent_id: str | None = None,
    sort_by: str = "order_index",  # name | course_count | created_at
    sort_order: str = "asc",  # asc | desc
    level: int | None = None,
):
    await authorization.require_role(["ADMIN"])
    return await service.get_categories_paginated_async(
        page=page,
        page_size=page_size,
        search=search,
        parent_id=parent_id,
        sort_by=sort_by,
        sort_order=sort_order,
        level=level,
    )


@router.get("/two_level")
async def get_parent_and_second_level_categories(
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_parent_and_second_level_categories()


@router.put("/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    schema: UpdateCategory,
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.update_category_async(category_id, schema)


@router.get("/{category_id}/last_order_index_same_level")
async def get_last_index(
    category_id: uuid.UUID,
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_last_order_index_same_level_async(category_id)


@router.delete("/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.delete_category_async(category_id)


@router.post("")
async def create_category(
    service: CategoryService = Depends(get_category_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
    schema: CreateCategory = Body(),
):
    await authorization.require_role(["ADMIN"])
    return await service.create_category_async(schema)
