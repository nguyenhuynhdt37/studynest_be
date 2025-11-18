from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.schemas.shares.wallets import PaymentCreateSchema
from app.services.shares.wallets import WalletsService

router = APIRouter(prefix="/wallets", tags=["Wallets"])


@router.get("")
async def get_wallet(
    payment_svc: WalletsService = Depends(WalletsService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user: User = await authorization_service.get_current_user()
    wallet = await payment_svc.get_by_user_id(user.id)
    if not wallet:
        raise HTTPException(404, "Không tìm thấy ví người dùng.")
    return wallet


@router.post("/create")
async def create_wallet_payment(
    request: Request,
    schema: PaymentCreateSchema,
    payment_svc: WalletsService = Depends(WalletsService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user: User = await authorization_service.get_current_user()
    result = await payment_svc.create_payment_async(
        request.app.state.http, schema=schema, user_id=user.id
    )
    return result


@router.get("/callback")
async def paypal_wallet_callback(
    request: Request,
    payment_svc: WalletsService = Depends(WalletsService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user: User = await authorization_service.get_current_user()
    token = request.query_params.get("token")
    if token is None:
        raise HTTPException(404, "khôn tìm thấy order_id")
    payer_id = request.query_params.get("PayerID")
    result = await payment_svc.paypal_callback_async(
        http=request.app.state.http, token=token, payer_id=payer_id, user=user
    )
    return result


@router.get("/cancel")
async def paypal_wallet_cancel(
    request: Request,
    payment_svc: WalletsService = Depends(WalletsService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    await authorization_service.get_current_user()
    token = request.query_params.get("token")
    if token is None:
        raise HTTPException(404, "khôn tìm thấy order_id")
    # payer_id = request.query_params.get("PayerID")
    result = await payment_svc.paypal_cancel_async(token)
    return result


@router.post("/retry_wallet_payment/{order_id}")
async def retry_wallet_payment_async(
    request: Request,
    order_id: str,
    payment_svc: WalletsService = Depends(WalletsService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    user: User = await authorization_service.get_current_user()
    result = await payment_svc.retry_wallet_payment_async(
        request.app.state.http, order_id=order_id, user_id=user.id
    )
    return result
