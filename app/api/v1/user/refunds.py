import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.schemas.shares.refund import RefundRequestCreate
from app.services.shares.refund import RefundService

router = APIRouter(prefix="/users/refunds", tags=["User • Refunds"])


# ============================================================
# 1) LẤY DANH SÁCH KHÓA HỌC CÒN CÓ THỂ REFUND
# ============================================================
@router.get("/my/refundable-courses")
async def get_my_refundable_courses(
    page: int = 1,
    limit: int = 10,
    refund_service: RefundService = Depends(RefundService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    """
    Danh sách khóa học user còn có thể refund.
    Điều kiện:
    - mua trong 3 ngày
    - completed
    - discounted_price > 0
    - instructor_earnings.holding
    - chưa từng tạo refund_request nào
    """

    user = await authorization_service.get_current_user()

    return await refund_service.get_user_refundable_courses(
        user_id=user.id,
        page=page,
        limit=limit,
    )


@router.get("/my-requests")
async def get_my_refund_requests(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    refund_status: str | None = None,
    course_id: uuid.UUID | None = None,
    instructor_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    service: RefundService = Depends(RefundService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    user = await authorization.get_current_user()
    return await service.get_user_refund_courses(
        user_id=user.id,
        page=page,
        limit=limit,
        search=search,
        refund_status=refund_status,
        course_id=course_id,
        instructor_id=instructor_id,
        date_from=date_from,
        date_to=date_to,
        order_by=order_by,
        order_dir=order_dir,
    )


@router.post("/request")
async def create_refund_request(
    body: RefundRequestCreate,
    service: RefundService = Depends(RefundService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await service.create_refund_request(
        user_id=user.id,
        purchase_item_id=body.purchase_item_id,
        reason=body.reason,
    )


@router.get("/requests/{refund_id}")
async def get_refund_request_detail(
    refund_id: uuid.UUID,
    service: RefundService = Depends(RefundService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    Xem chi tiết 1 yêu cầu hoàn tiền của học viên.

    - refund_id: ID của yêu cầu hoàn tiền
    - User phải đăng nhập
    - Trả về đủ: refund + purchase + course + instructor + earnings
    """
    user = await authorization.get_current_user()

    return await service.get_refund_request_detail_async(
        refund_id=refund_id,
        viewer_id=user.id,
        role="USER",
    )
