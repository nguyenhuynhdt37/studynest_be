import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.services.shares.transaction import TransactionsService

router = APIRouter(prefix="/lecturer/transactions", tags=["Lecturer Transactions"])


@router.get("")
async def lecturer_get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    type_: Optional[str] = Query(None, alias="type"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
):
    """
    Lấy danh sách giao dịch của GIẢNG VIÊN kèm FULL DETAIL:
    - transaction (earning_release, earning_payout, earning_refund)
    - earnings
    - student
    - course
    - purchase_items
    - discount_history + discount_info
    """
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    instructor = await authorization_service.require_role(["LECTURER"])
    # ============================
    return await transactions_service.get_lecturer_transactions(
        instructor_id=instructor.id,
        page=page,
        limit=limit,
        search=search,
        status=status,
        type_=type_,
        date_from=date_from,
        date_to=date_to,
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
    user = await auth.require_role(["LECTURER"])
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    return await service.get_instructor_pending_earnings(
        instructor_id=user.id,
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
    lecturer = await auth.require_role(["LECTURER"])
    return await service.get_holding_students_minimal(
        instructor_id=lecturer.id,
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
    lecturer = await auth.require_role(["LECTURER"])
    return await service.get_holding_courses_minimal(
        instructor_id=lecturer.id,
        search=search,
        limit=limit,
    )


@router.get("/{transaction_id}")
async def get_lecturer_transaction_detail(
    transaction_id: uuid.UUID,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
):
    """
    Lấy chi tiết giao dịch của GIẢNG VIÊN theo ID giao dịch
    """
    instructor = await authorization_service.require_role(["LECTURER"])
    return await transactions_service.get_user_transaction_detail(
        user_id=instructor.id,
        transaction_id=transaction_id,
    )
