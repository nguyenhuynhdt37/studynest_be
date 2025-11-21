from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.shares.payout import PayoutService
from app.services.shares.paypal_service import PayPalService

router = APIRouter(prefix="/lecturer/payout", tags=["lecturer • Payout"])


@router.get("/callback")
async def paypal_wallet_callback(
    request: Request,
    payout_service: PayoutService = Depends(PayoutService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    pass
    user: User = await authorization_service.require_role(["LECTURER"])
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if code is None or state is None:
        raise HTTPException(400, "Thiếu code hoặc state từ PayPal.")
    paypal = PayPalService(request.app.state.http)
    result = await payout_service.paypal_connect_callback_async(
        code,
        paypal,
        user,
        state,
    )
    return result
