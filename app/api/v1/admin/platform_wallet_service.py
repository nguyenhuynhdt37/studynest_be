import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.libs.formats.datetime import to_vietnam_naive
from app.services.admin.platform_wallet_service import PlatformWalletService

router = APIRouter(prefix="/admin/platform-wallet", tags=["Platform Wallet"])


@router.get("/overview")
async def get_wallet_overview(
    service: PlatformWalletService = Depends(
        PlatformWalletService
    ),  # pyright: ignore[reportUndefinedVariable]
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_platform_wallet_with_recent_history()


@router.get("/history")
async def admin_get_platform_wallet_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    type_: Optional[str] = Query(None, alias="type"),
    transaction_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime.datetime] = None,
    date_to: Optional[datetime.datetime] = None,
    sort_by: str = "created_at",
    order_dir: str = "desc",
    service: PlatformWalletService = Depends(),
):
    # chuẩn hóa datetime (UTC+7 naive)
    date_from = await to_vietnam_naive(date_from)
    date_to = await to_vietnam_naive(date_to)

    return await service.get_platform_wallet_history_admin_async(
        page=page,
        limit=limit,
        search=search,
        type_=type_,
        transaction_id=transaction_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order_dir=order_dir,
    )


@router.get("/history/{history_id}")
async def admin_get_platform_wallet_transaction_detail(
    history_id: uuid.UUID,
    service: PlatformWalletService = Depends(),
):
    return await service.get_platform_wallet_transaction_detail_admin_async(history_id)
