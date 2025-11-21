from fastapi import APIRouter, Query, Request

from app.services.shares.paypal_service import PayPalService

router = APIRouter(prefix="/test", tags=["test"])


@router.get("/payout")
async def test_payout(
    request: Request,
):
    paypal_service = PayPalService(http=request.app.state.http)
    return await paypal_service.payout(
        receiver_email="sb-euk47j43769608@personal.example.com",
        amount="10.00",
        currency="USD",
        note="Test payout",
    )


@router.get("/get_payout_status")
async def get_payout_status(
    request: Request,
    payout_batch_id: str = Query(...),
):
    paypal_service = PayPalService(http=request.app.state.http)
    return await paypal_service.get_payout_status(payout_batch_id=payout_batch_id)
