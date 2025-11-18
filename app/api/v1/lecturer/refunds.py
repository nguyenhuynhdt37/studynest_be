import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.schemas.shares.refund import RefundReviewSchema
from app.services.shares.notification import NotificationService
from app.services.shares.refund import RefundService

router = APIRouter(prefix="/lecturer/refunds", tags=["lecturer • Refunds"])


@router.get("/requests")
async def list_refund_requests(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    refund_status: str | None = None,
    course_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    instructor_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    service: RefundService = Depends(),
    auth: AuthorizationService = Depends(),
):
    reviewer = await auth.require_role(["LECTURER"])
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    return await service.get_all_refund_status_async(
        reviewer_id=reviewer.id,
        role="LECTURER",
        page=page,
        limit=limit,
        search=search,
        refund_status=refund_status,
        course_id=course_id,
        student_id=student_id,
        instructor_id=reviewer.id,
        date_from=date_from,
        date_to=date_to,
        order_by=order_by,
        order_dir=order_dir,
    )


@router.get("/requests/{refund_id}")
async def get_refund_request_detail(
    refund_id: uuid.UUID,
    service: RefundService = Depends(),
    auth: AuthorizationService = Depends(),
):
    user = await auth.require_role(["LECTURER"])
    return await service.get_refund_request_detail_async(
        refund_id=refund_id,
        viewer_id=user.id,
        role="LECTURER",
    )


# ==========================================================
# LECTURER DUYỆT / TỪ CHỐI YÊU CẦU HOÀN TIỀN
# ==========================================================
@router.post("/{refund_id}/lecturer-review", summary="Giảng viên duyệt yêu cầu refund")
async def lecturer_review_refund(
    refund_id: uuid.UUID,
    body: RefundReviewSchema,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: RefundService = Depends(RefundService),
    notification_service: NotificationService = Depends(NotificationService),
):
    lecturer = await auth.require_role(["LECTURER"])

    return await service.review_refund_request_async(
        refund_id=refund_id,
        reviewer_id=lecturer.id,
        role="LECTURER",
        action=body.action,
        reason=body.reason,
        notification_service=notification_service,
    )
