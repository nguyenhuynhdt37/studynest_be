from fastapi import APIRouter, Depends

from app.core.deps import AuthorizationService
from app.services.shares.wallets import WalletsService

router = APIRouter(prefix="/lecturer/wallets", tags=["LECTURER Wallets"])


@router.get("/lecturer/wallet")
async def get_lecturer_wallet(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    wallet_service: WalletsService = Depends(WalletsService),
):
    lecturer = await authorization_service.require_role(["LECTURER"])
    wallet = await wallet_service.get_by_user_id(lecturer.id)
    return wallet
