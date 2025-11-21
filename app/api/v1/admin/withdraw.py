import uuid

from fastapi import APIRouter, Body, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.shares.withdraw import WithdrawApproveDenySchema
from app.services.shares.notification import NotificationService
from app.services.shares.withdraw import WithdrawService

router = APIRouter(prefix="/admin/withdraw", tags=["ADMIN withdraw"])


@router.get("")
async def list_withdraw_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    status: str | None = None,
    lecturer_id: uuid.UUID | None = None,
    search: str | None = None,
    order_by: str = "requested_at",
    order_dir: str = "desc",
    auth: AuthorizationService = Depends(AuthorizationService),
    service: WithdrawService = Depends(WithdrawService),
):
    await auth.require_role(["ADMIN"])
    result = await service.get_withdraw_list_async(
        user=None,
        role="ADMIN",
        page=page,
        limit=limit,
        status=status,
        lecturer_id=lecturer_id,
        search=search,
        order_by=order_by,
        order_dir=order_dir,
    )
    return result


@router.post("/approve_deny")
async def approve_or_deny_withdraw_request(
    schema: WithdrawApproveDenySchema = Body(...),
    auth: AuthorizationService = Depends(AuthorizationService),
    service: WithdrawService = Depends(WithdrawService),
    notification_service: NotificationService = Depends(NotificationService),
):
    await auth.require_role(["ADMIN"])
    return await service.approve_or_deny_withdrawals_async(
        approve=schema.approve,
        withdraw_ids=schema.withdraw_ids,
        all_pending=schema.all_pending,
        reason=schema.reason,
        lecturer_id=schema.lecturer_id,
        notification_service=notification_service,
    )


@router.get("/lecturers")
async def search_withdraw_lecturers(
    q: str | None = None,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: WithdrawService = Depends(WithdrawService),
):
    await auth.require_role(["ADMIN"])
    return await service.search_withdraw_lecturers_async(keyword=q, limit=10)


@router.get("/{withdraw_id}")
async def get_withdraw_request_detail(
    withdraw_id: uuid.UUID,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: WithdrawService = Depends(WithdrawService),
):
    await auth.require_role(["ADMIN"])
    return await service.get_withdraw_request_by_id_async(withdraw_id)
