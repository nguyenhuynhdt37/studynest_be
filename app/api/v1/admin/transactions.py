import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.services.shares.transaction import TransactionsService

router = APIRouter(prefix="/admin/transactions", tags=["Admin Transactions"])


@router.get("")
async def admin_get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    type_: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    direction: Optional[str] = None,
    method: Optional[str] = None,
    gateway: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    course_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: str = "created_at",
    order_dir: str = "desc",
    service: TransactionsService = Depends(),
):
    """
    Admin lấy danh sách giao dịch đầy đủ (lọc + tìm kiếm + phân trang).
    """
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    return await service.get_transactions_admin_async(
        page=page,
        limit=limit,
        search=search,
        type_=type_,
        status=status,
        direction=direction,
        method=method,
        gateway=gateway,
        user_id=user_id,
        course_id=course_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order_dir=order_dir,
    )


# ============================================================
# 1) LẤY DANH SÁCH HỌC VIÊN ĐANG HOLD
# ============================================================
@router.get("/students")
async def get_holding_students(
    search: str | None = Query(None, description="Tìm kiếm theo tên học viên"),
    limit: int = Query(10, ge=1, le=50),
    service: TransactionsService = Depends(TransactionsService),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    await auth.require_role(["ADMIN"])
    return await service.get_holding_students_minimal(
        instructor_id=None,
        search=search,
        limit=limit,
        role="ADMIN",
    )


# ============================================================
# 1) LẤY DANH SÁCH HỌC VIÊN ĐANG HOLD
# ============================================================
@router.get("/lecturers")
async def get_holding_lecturer_minimal(
    search: str | None = Query(None, description="Tìm kiếm theo tên học viên"),
    limit: int = Query(10, ge=1, le=50),
    service: TransactionsService = Depends(TransactionsService),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    await auth.require_role(["ADMIN"])
    return await service.get_holding_lecturer_minimal(
        search=search,
        limit=limit,
    )


# ============================================================
# 2) LẤY DANH SÁCH KHÓA HỌC ĐANG HOLD
# ============================================================
@router.get("/courses")
async def get_holding_courses(
    search: str | None = Query(None, description="Tìm kiếm theo tên khóa học"),
    limit: int = Query(10, ge=1, le=50),
    service: TransactionsService = Depends(TransactionsService),
    auth: AuthorizationService = Depends(AuthorizationService),
):
    await auth.require_role(["ADMIN"])
    return await service.get_holding_courses_minimal(
        instructor_id=None,
        search=search,
        limit=limit,
        role="ADMIN",
    )


@router.get("/earnings/holding")
async def get_instructor_holding_earnings(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    course_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order_by: str = "hold_until",
    order_dir: str = "asc",
    service: TransactionsService = Depends(),
    auth: AuthorizationService = Depends(),
):
    await auth.require_role(["ADMIN"])
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    return await service.get_instructor_pending_earnings(
        instructor_id=None,
        page=page,
        limit=limit,
        search=search,
        status=status,
        course_id=course_id,
        student_id=student_id,
        date_from=date_from,
        date_to=date_to,
        order_by=order_by,
        order_dir=order_dir,
        role="ADMIN",
    )


@router.get("/{transaction_id}")
async def admin_get_transaction_detail(
    transaction_id: uuid.UUID,
    service: TransactionsService = Depends(),
):
    return await service.get_transaction_detail_admin_async(transaction_id)
