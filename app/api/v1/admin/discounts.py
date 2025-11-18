import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.shares.discounts import DiscountCreateSchema, DiscountEditSchema
from app.services.shares.discounts import DiscountService

router = APIRouter(prefix="/admin/discounts", tags=["Admin Discounts"])


@router.post("", summary="Tạo mã giảm giá")
async def create_discount(
    schema: DiscountCreateSchema,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    admin = await authorization.require_role(["ADMIN"])
    return await service.create_discount_async(
        schema, created_by=admin.id, created_role="ADMIN"
    )


@router.get("", summary="Lấy danh sách mã giảm giá")
async def get_discounts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(""),
    applies_to: str | None = Query(None),
    discount_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("created_at"),
    validity: str | None = Query(None),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["ADMIN"])
    return await service.get_discounts_async(
        lecturer,
        "ADMIN",
        page,
        limit,
        search,
        applies_to,
        discount_type,
        is_active,
        validity,
        sort_by,
        order_dir,
    )


# ==============================
# GET WEAK COURSES FOR DISCOUNT
# ================================
@router.get("/weak-courses")
async def get_weak_courses(
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(dependency=AuthorizationService),
):
    """
    Danh sách khóa học yếu:
    - rating thấp
    - enroll thấp (lấy trực tiếp từ bảng Courses)
    - views thấp
    - revenue thấp
    """
    await authorization.require_role(["ADMIN"])

    return await service.get_weak_courses_async()


@router.get("/courses")
async def admin_get_discount_courses(
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    service: DiscountService = Depends(DiscountService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    ADMIN lấy danh sách khóa học để tạo mã giảm giá.
    Xem được tất cả course.
    """
    await authorization.require_role(["ADMIN"])

    return await service.get_discount_course_list_async(
        page=page,
        limit=limit,
        search=search,
        instructor_id=None,  # admin lấy toàn bộ
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
    user = await authorization.require_role(["ADMIN"])
    # Lấy vai trò user

    return await service.get_discount_detail_async(
        discount_id=discount_id,
        user=user,
        role="ADMIN",
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
    user = await authorization.require_role(["ADMIN"])
    role = "ADMIN"

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
    user = await authorization.require_role(["ADMIN"])
    return await service.delete_discount_async(
        discount_id=discount_id,
        user=user,
        role="ADMIN",
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
    user = await authorization.require_role(["ADMIN"])

    return await service.toggle_discount_active_async(
        discount_id=discount_id,
        user=user,
        role="ADMIN",
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
    user = await authorization.require_role(["ADMIN"])
    return await service.get_discount_edit_data_async(
        discount_id=discount_id,
        user=user,
        role="ADMIN",
    )


# app/api/v1/admin/discounts.py
