import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.schemas.shares.transactions import PurchaseCheckoutSchema
from app.services.shares.discounts import DiscountService
from app.services.shares.transaction import TransactionsService
from app.services.shares.wallets import WalletsService

router = APIRouter(prefix="/user/transaction", tags=["User Transactions"])


@router.get("")
async def get_my_transactions(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    type_: str | None = None,
    method: str | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
):
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    user = await authorization_service.get_current_user()
    return await transactions_service.get_user_transactions(
        user_id=user.id,
        page=page,
        limit=limit,
        search=search,
        status=status,
        type_=type_,
        method=method,
        order_by=order_by,
        order_dir=order_dir,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/top5")
async def get_my_transactions_top_5(
    page: int = 1,
    limit: int = 5,
    search: str | None = None,
    status: str | None = None,
    type_: str | None = None,
    method: str | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
):
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)
    user = await authorization_service.get_current_user()
    return await transactions_service.get_user_transactions(
        user_id=user.id,
        page=page,
        limit=limit,
        search=search,
        status=status,
        type_=type_,
        method=method,
        order_by=order_by,
        order_dir=order_dir,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/courses/checkout")
async def checkout(
    schema: PurchaseCheckoutSchema,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
    wallets_service: WalletsService = Depends(WalletsService),
    discount_service: DiscountService = Depends(DiscountService),
):
    user = await authorization_service.get_current_user()
    return await transactions_service.checkout_wallet_async(
        user=user,
        course_ids=schema.course_ids,
        discount_code=schema.discount_code,
        wallets_service=wallets_service,
        discount_service=discount_service,
    )


@router.get("/{transaction_id}")
async def get_transaction_detail(
    transaction_id: uuid.UUID,
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    transactions_service: TransactionsService = Depends(TransactionsService),
):
    user = await authorization_service.get_current_user()

    return await transactions_service.get_user_transaction_detail(
        transaction_id=transaction_id,
        user_id=user.id,
    )
