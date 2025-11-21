import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.services.shares.notification import NotificationService
from app.services.shares.withdraw import WithdrawService

router = APIRouter(prefix="/lecturer/withdraw", tags=["LECTURER withdraw"])


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
    user = await auth.require_role(["ADMIN", "LECTURER"])
    result = await service.get_withdraw_list_async(
        user=user,
        role="LECTURER",  # hoặc auth lấy role ra
        page=page,
        limit=limit,
        status=status,
        lecturer_id=lecturer_id,
        search=search,
        order_by=order_by,
        order_dir=order_dir,
    )
    return result


@router.post("/request")
async def request_withdraw(
    amount: float,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    withdraw_service: WithdrawService = Depends(WithdrawService),
    notification_service: NotificationService = Depends(NotificationService),
):
    lecturer = await authorization_service.require_role(["LECTURER"])
    return await withdraw_service.request_withdraw_async(
        lecturer, amount, notification_service
    )


@router.get("/check-can-request")
async def check_can_request_withdraw(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    withdraw_service: WithdrawService = Depends(WithdrawService),
):
    lecturer = await authorization_service.require_role(["LECTURER"])
    return await withdraw_service.check_can_withdraw_request_async(lecturer)
