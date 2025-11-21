from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

import httpx
import jwt  # dùng để decode id_token

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
    - LOGIN / CONNECT PAYPAL: OAuth2 (authorization_code + id_token)
    - Token cache nội bộ cho Orders / Payouts
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
        """
        Lấy app access_token (client_credentials) dùng cho:
        - Orders API
        - Payouts API
        KHÔNG dùng cho OAuth login.
        """
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
        if not self._access_token:
            # đề phòng dev quên gọi _ensure_token()
            raise PayPalError(
                "Access token chưa được khởi tạo. Gọi _ensure_token() trước."
            )
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

    # =========================================================
    # OAUTH LOGIN – ĐỔI CODE LẤY TOKEN + ID_TOKEN
    # =========================================================
    async def oauth_exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Đổi authorization_code (trả về ở callback) sang:
        - access_token (cho user)
        - id_token (JWT OpenID chứa email, payer_id, name)
        """
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
            timeout=self.default_timeout,
        )
        if resp.status_code != 200:
            raise PayPalError(f"Exchange token lỗi: {resp.status_code} {resp.text}")

        return resp.json()

    @staticmethod
    def decode_id_token(id_token: str) -> Dict[str, Any]:
        """
        Giải mã id_token (JWT) KHÔNG verify signature (sandbox / debug).
        Khi production thì verify theo JWKs của PayPal.
        """
        return jwt.decode(id_token, options={"verify_signature": False})

    async def get_userinfo_from_code(   
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Chuẩn hóa lấy thông tin người dùng PayPal từ code:

        - Trường hợp 1: Flow OpenID → có id_token → decode trực tiếp
        - Trường hợp 2: Flow Merchant Onboarding → KHÔNG có id_token
        → gọi /v1/identity/oauth2/userinfo lấy email + payer_id
        """

        token_data = await self.oauth_exchange_code(code, redirect_uri)

        # Ưu tiên lấy từ id_token nếu có
        id_token = token_data.get("id_token")

        if id_token:
            payload = self.decode_id_token(id_token)

            return {
                "email": payload.get("email"),
                "payer_id": payload.get("payer_id") or payload.get("user_id"),
                "name": payload.get("name"),
                "raw_payload": payload,
                "token_data": token_data,
                "source": "id_token",
            }

        # ============================
        # Fallback: Merchant Onboarding (no id_token)
        # ============================

        access_token = token_data.get("access_token")
        if not access_token:
            raise PayPalError("Không tìm thấy access_token trong phản hồi PayPal.")

        # Gọi userinfo API
        r = await self.http.get(
            f"{self.base_url}/v1/identity/oauth2/userinfo?schema=openid",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if r.status_code != 200:
            raise PayPalError(f"Lỗi gọi userinfo PayPal: {r.text}")

        info = r.json()

        return {
            "email": info.get("email"),
            "payer_id": info.get("user_id"),
            "name": info.get("name"),
            "raw_payload": info,
            "token_data": token_data,
            "source": "userinfo",
        }
