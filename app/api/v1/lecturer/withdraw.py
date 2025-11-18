from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.services.shares.notification import NotificationService
from app.services.shares.withdraw import WithdrawService

router = APIRouter(prefix="/lecturer/withdraw", tags=["LECTURER Wallets"])


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
