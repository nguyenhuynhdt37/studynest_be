import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.shares.discounts import DiscountCreateSchema, DiscountEditSchema
from app.services.shares.discounts import DiscountService

router = APIRouter(prefix="/lecturer/discounts", tags=["Lecturer Discounts"])


@router.post("", summary="Tạo mã giảm giá")
async def create_discount(
    schema: DiscountCreateSchema,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await service.create_discount_async(
        schema, created_by=lecturer.id, created_role="LECTURER"
    )


@router.get("", summary="Lấy danh sách mã giảm giá")
async def get_discounts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(""),
    discount_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("created_at"),
    validity: str | None = Query(None),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_discounts_async(
        lecturer,
        "LECTURER",
        page,
        limit,
        search,
        "course",
        discount_type,
        is_active,
        validity,
        sort_by,
        order_dir,
    )


# ================================
# GET DETAIL DISCOUNT
# ================================
@router.get("/{discount_id}")
async def get_discount_detail(
    discount_id: uuid.UUID,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Lấy chi tiết mã giảm giá:
    - ADMIN xem tất cả
    - LECTURER chỉ xem được mã của chính họ
    """
    user = await authorization.require_role(["LECTURER"])
    # Lấy vai trò user

    return await service.get_discount_detail_async(
        discount_id=discount_id,
        user=user,
        role="LECTURER",
    )


# ==============================
# UPDATE DISCOUNT
# ================================
@router.put("/{discount_id}")
async def update_discount(
    discount_id: uuid.UUID,
    schema: DiscountEditSchema,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Cập nhật mã giảm giá:
    - ADMIN cập nhật tất cả
    - LECTURER chỉ cập nhật mã giảm của chính họ
    - Không cho sửa code/type nếu mã đã được sử dụng
    """
    user = await authorization.require_role(["LECTURER"])
    role = "LECTURER"

    return await service.edit_discount_async(
        discount_id=discount_id,
        schema=schema,
        user=user,
        role=role,
    )


@router.delete("/{discount_id}")
async def delete_discount(
    discount_id: uuid.UUID,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Xóa mã giảm giá:
    - Chỉ xóa khi chưa từng được sử dụng
    - ADMIN xóa được tất cả
    - LECTURER chỉ xóa được mã mình tạo
    """
    user = await authorization.require_role(["LECTURER"])
    return await service.delete_discount_async(
        discount_id=discount_id,
        user=user,
        role="LECTURER",
    )


# ==============================
# TOGGLE ACTIVE / INACTIVE DISCOUNT
# ================================
@router.patch("/{discount_id}/toggle")
async def toggle_discount(
    discount_id: uuid.UUID,
    is_active: bool,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Bật / Tắt trạng thái mã giảm giá:
    - ADMIN được bật/tắt tất cả mã
    - LECTURER chỉ được bật/tắt mã do mình tạo
    """
    user = await authorization.require_role(["LECTURER"])

    return await service.toggle_discount_active_async(
        discount_id=discount_id,
        user=user,
        role="LECTURER",
        is_active=is_active,
    )


# ==============================
# GET DISCOUNT EDIT DATA
# ================================
@router.get("/{discount_id}/edit")
async def get_discount_edit_data(
    discount_id: uuid.UUID,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Lấy dữ liệu chi tiết để hiển thị form edit mã giảm giá:
    - ADMIN xem được tất cả
    - LECTURER chỉ xem mã do chính họ tạo
    """
    user = await authorization.require_role(["LECTURER"])
    return await service.get_discount_edit_data_async(
        discount_id=discount_id,
        user=user,
        role="LECTURER",
    )
