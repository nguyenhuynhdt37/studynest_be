from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

import httpx

from app.core.settings import settings
from app.db.models.database import Transactions
from app.libs.formats.datetime import now as get_now

MAX_PENDING_HOURS = 3


class PayPalError(RuntimeError):
    pass


class PayPalService:
    """
    Service PayPal:
    - NẠP TIỀN: Redirect flow (Orders API)
    - RÚT TIỀN: Payouts API
    - Token cache nội bộ
    """

    def __init__(self, http: httpx.AsyncClient, timeout: float = 30.0):
        self.http = http
        self.base_url = settings.PAYPAL_BASE_URL.rstrip("/")
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.default_timeout = timeout

        self._access_token: Optional[str] = None
        self._token_expire_at: float = 0.0

    # =========================================================
    # INTERNAL
    # =========================================================
    async def _ensure_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expire_at - 15:
            return self._access_token

        resp = await self.http.post(
            f"{self.base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=self.default_timeout,
        )
        if resp.status_code != 200:
            raise PayPalError(f"Auth lỗi: {resp.status_code} {resp.text}")

        data = resp.json()
        self._access_token = data.get("access_token")
        self._token_expire_at = now + int(data.get("expires_in", 300))
        if not self._access_token:
            raise PayPalError("Không nhận được access_token từ PayPal.")

        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _idempotency_key() -> str:
        return str(uuid.uuid4())

    # =========================================================
    # NẠP TIỀN (Checkout Orders API)
    # =========================================================
    async def create_order_redirect(
        self,
        *,
        value: str,
        currency: str = "USD",
        description: str = "Thanh toán đơn hàng",
        return_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:

        await self._ensure_token()
        headers = self._headers()
        headers["PayPal-Request-Id"] = self._idempotency_key()

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {"currency_code": currency, "value": value},
                    "description": description,
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }

        resp = await self.http.post(
            f"{self.base_url}/v2/checkout/orders",
            headers=headers,
            json=payload,
            timeout=self.default_timeout,
        )

        if resp.status_code != 201:
            raise PayPalError(f"Tạo order lỗi: {resp.status_code} {resp.text}")
        return resp.json()

    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        await self._ensure_token()
        headers = self._headers()
        headers["PayPal-Request-Id"] = self._idempotency_key()

        resp = await self.http.post(
            f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
            headers=headers,
            timeout=self.default_timeout,
        )

        if resp.status_code not in (200, 201):
            raise PayPalError(f"Capture lỗi: {resp.status_code} {resp.text}")

        return resp.json()

    async def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        await self._ensure_token()
        headers = self._headers()

        resp = await self.http.get(
            f"{self.base_url}/v2/checkout/orders/{order_id}",
            headers=headers,
            timeout=self.default_timeout,
        )

        if resp.status_code != 200:
            raise PayPalError(
                f"Lấy thông tin order lỗi: {resp.status_code} {resp.text}"
            )

        return resp.json()

    # =========================================================
    # CHECK CÓ ĐƯỢC RETRY PENDING KHÔNG
    # =========================================================
    async def can_retry_payment(self, transaction: Transactions) -> bool:
        if transaction.status != "pending":
            return False
        now = get_now()
        if not transaction.created_at:
            return False
        delta = now - transaction.created_at
        return delta.total_seconds() <= MAX_PENDING_HOURS * 3600

    # =========================================================
    # RÚT TIỀN (Payouts API)
    # =========================================================
    async def payout(
        self,
        *,
        receiver_email: str,
        amount: str,
        currency: str = "USD",
        note: str = "Instructor withdrawal",
    ) -> Dict[str, Any]:
        """
        Tạo payout gửi tiền đến PayPal của giảng viên.
        Trả về batch_id -> dùng để kiểm tra trạng thái.
        """

        await self._ensure_token()
        headers = self._headers()
        headers["PayPal-Request-Id"] = self._idempotency_key()

        payload = {
            "sender_batch_header": {
                "recipient_type": "EMAIL",
                "email_subject": "You have a payout!",
                "email_message": "Bạn vừa nhận được tiền!",
            },
            "items": [
                {
                    "note": note,
                    "amount": {"value": amount, "currency": currency},
                    "receiver": receiver_email,
                    "sender_item_id": str(uuid.uuid4()),
                }
            ],
        }

        resp = await self.http.post(
            f"{self.base_url}/v1/payments/payouts",
            headers=headers,
            json=payload,
            timeout=self.default_timeout,
        )

        if resp.status_code not in (201, 202):
            raise PayPalError(f"Payout lỗi: {resp.status_code} {resp.text}")

        return resp.json()

    # =========================================================
    # KIỂM TRA TRẠNG THÁI PAYOUT
    # =========================================================
    async def get_payout_status(self, payout_batch_id: str) -> Dict[str, Any]:
        """
        Lấy trạng thái payout:
        - SUCCESS
        - PENDING
        - FAILED
        """

        await self._ensure_token()
        headers = self._headers()

        resp = await self.http.get(
            f"{self.base_url}/v1/payments/payouts/{payout_batch_id}",
            headers=headers,
            timeout=self.default_timeout,
        )

        if resp.status_code != 200:
            raise PayPalError(
                f"Lấy trạng thái payout lỗi: {resp.status_code} {resp.text}"
            )

        return resp.json()

    async def oauth_exchange_code(self, code: str, redirect_uri: str):
        url = f"{self.base_url}/v1/oauth2/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }

        resp = await self.http.post(
            url,
            data=data,
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise PayPalError(f"Exchange token lỗi: {resp.text}")

        return resp.json()

    async def decode_id_token(self, id_token: str):
        import jwt

        return jwt.decode(id_token, options={"verify_signature": False})
