import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService, get_embedding_service
from app.core.settings import settings
from app.db.models.database import (
    PlatformWalletHistory,
    PlatformWallets,
    Transactions,
    User,
    Wallets,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_utc_naive
from app.schemas.shares.notification import NotificationCreateSchema
from app.schemas.shares.wallets import PaymentCreateSchema
from app.services.shares.currency_service import convert_vnd_to_usd
from app.services.shares.notification import NotificationService
from app.services.shares.paypal_service import PayPalService

MAX_PENDING_HOURS = 3


class WalletsService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db

    def _payment_redirect_url(
        self,
        transaction: Transactions,
        status: str,
        order_id: str,
    ) -> str:
        origin = (transaction.return_origin or settings.FRONTEND_URL or "").rstrip("/")
        redirect = transaction.return_pathname or ""

        if not origin:
            origin = settings.FRONTEND_URL.rstrip("/")

        is_web_url = origin.startswith("http://") or origin.startswith("https://")
        base = f"{origin}/transaction" if is_web_url else origin
        separator = "&" if "?" in base else "?"

        return (
            f"{base}{separator}status={status}"
            f"&order_id={order_id}"
            f"&redirect={redirect}"
        )

    async def create_payment_async(
        self,
        http,
        schema: PaymentCreateSchema,
        user_id: uuid.UUID,
    ):
        """
        Tạo giao dịch nạp ví PayPal (redirect flow)
        - Quy đổi VNĐ -> USD
        - Gọi PayPalService.create_order_redirect()
        - Trả về approve_url để FE redirect
        """
        try:
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == user_id)
            )
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == user_id)
            )
            if wallet is None:
                wallet = Wallets(
                    user_id=user_id,
                    balance=0,
                    currency="VND",
                    created_at=await to_utc_naive(get_now()),
                    updated_at=await to_utc_naive(get_now()),
                )
                self.db.add(wallet)
                await self.db.commit()
                await self.db.flush(wallet)

            paypal = PayPalService(http)

            # 1️⃣ Quy đổi VNĐ sang USD
            usd_value = await convert_vnd_to_usd(schema.amount_vnd)
            if not usd_value or usd_value <= 0:
                raise HTTPException(
                    status_code=400, detail="Tỷ giá không hợp lệ hoặc bằng 0."
                )

            usd_value = Decimal(str(usd_value)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            usd_str = f"{usd_value:.2f}"
            # 2️⃣ Tạo order redirect PayPal
            return_url = f"{settings.BACKEND_URL}/api/v1/wallets/callback"
            cancel_url = f"{settings.BACKEND_URL}/api/v1/wallets/cancel"

            result = await paypal.create_order_redirect(
                value=usd_str,
                currency="USD",
                description=f"Nạp ví {schema.amount_vnd:,} VNĐ",
                return_url=return_url,
                cancel_url=cancel_url,
            )

            order_id = result.get("id")
            status = result.get("status")
            approve_link = next(
                (
                    link["href"]
                    for link in result.get("links", [])
                    if link["rel"] == "approve"
                ),
                None,
            )

            if not order_id:
                raise HTTPException(
                    status_code=502, detail="PayPal không trả về order_id."
                )
            if not approve_link:
                raise HTTPException(
                    status_code=502,
                    detail="Không tìm thấy liên kết approve của PayPal.",
                )

            transaction = Transactions(
                id=uuid.uuid4(),
                user_id=user_id,
                amount=Decimal(schema.amount_vnd),
                currency="VND",
                type="deposit",
                ref_id=wallet.id,
                direction="in",
                method="paypal",
                gateway="paypal",
                order_id=order_id,
                status="pending",
                return_pathname=schema.return_pathname,
                return_origin=schema.return_origin,
                description=f"Nạp {schema.amount_vnd:,} VNĐ qua PayPal (~{usd_value:.2f} USD)",
                created_at=await to_utc_naive(get_now()),
            )
            self.db.add(transaction)
            await self.db.commit()

            return {
                "order_id": order_id,
                "status": status,
                "amount_vnd": str(schema.amount_vnd),
                "amount_usd": usd_str,
                "approve_url": approve_link,
                "user_id": str(user_id),
            }

        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi tạo thanh toán: {e}")

    async def paypal_callback_async(
        self, http, token: str, payer_id: str | None = None
    ):
        """
        Callback PayPal sau khi thanh toán:
        - Capture PayPal
        - Cập nhật giao dịch
        - Cộng ví user
        - Cộng ví hệ thống
        - Ghi platform_wallet_history
        - Notify user + admin
        - Redirect FE
        """
        if not token:
            raise HTTPException(400, "Thiếu token (order_id).")

        paypal = PayPalService(http)

        # ========================
        # 1) CAPTURE ORDER
        # ========================
        try:
            capture_result = await paypal.capture_order(order_id=token)
        except Exception as e:
            raise HTTPException(502, f"Lỗi capture PayPal: {e}")

        status = capture_result.get("status", "").upper()
        if status != "COMPLETED":
            raise HTTPException(400, f"Giao dịch chưa hoàn tất ({status}).")

        # ========================
        # 2) LẤY TRANSACTION
        # ========================
        query = await self.db.execute(
            select(Transactions).where(Transactions.order_id == token)
        )
        transaction: Transactions | None = query.scalar_one_or_none()

        if not transaction:
            raise HTTPException(404, "Không tìm thấy giao dịch.")

        # Nếu đã completed → chống double callback
        if transaction.status == "completed":
            return RedirectResponse(
                url=self._payment_redirect_url(transaction, "success", token)
            )

        # ========================
        # 3) LẤY VÍ USER
        # ========================
        wallet = (
            await self.db.execute(
                select(Wallets)
                .where(Wallets.user_id == transaction.user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if not wallet:
            raise HTTPException(404, "Không tìm thấy ví người dùng.")

        user = await self.db.scalar(select(User).where(User.id == transaction.user_id))

        # ========================
        # 4) LẤY VÍ HỆ THỐNG (1 RECORD)
        # ========================
        platform_wallet = (
            await self.db.execute(select(PlatformWallets).with_for_update())
        ).scalar_one_or_none()

        if not platform_wallet:
            platform_wallet = PlatformWallets(
                balance=Decimal(0),
                total_in=Decimal(0),
                total_out=Decimal(0),
                holding_amount=Decimal(0),
                platform_fee_total=Decimal(0),
            )
            self.db.add(platform_wallet)
            await self.db.flush()

        # ========================
        # 5) TIỀN NẠP
        # ========================
        amount = transaction.amount or Decimal(0)
        now = await to_utc_naive(get_now())

        # Cập nhật ví user
        wallet.balance = (wallet.balance or 0) + amount
        wallet.total_in = (wallet.total_in or 0) + amount
        wallet.last_transaction_at = now
        wallet.updated_at = now

        # Cập nhật ví hệ thống
        platform_wallet.balance = (platform_wallet.balance or 0) + amount
        platform_wallet.total_in = (platform_wallet.total_in or 0) + amount
        platform_wallet.updated_at = now

        # ========================
        # 6) GHI LOG SỔ CÁI (platform_wallet_history)
        # ========================
        log = PlatformWalletHistory(
            wallet_id=platform_wallet.id,
            type="in",
            amount=amount,
            related_transaction_id=transaction.id,
            note="Nạp tiền PayPal vào hệ thống",
        )
        self.db.add(log)

        # ========================
        # 7) UPDATE TRANSACTION
        # ========================
        try:
            capture_id = capture_result["purchase_units"][0]["payments"]["captures"][0][
                "id"
            ]
        except Exception:
            capture_id = None

        transaction.transaction_code = capture_id
        transaction.status = "completed"
        transaction.confirmed_at = now
        transaction.updated_at = now

        # ========================
        # 8) NOTIFY USER
        # ========================
        notification_service = NotificationService(self.db)

        await notification_service.create_notification_async(
            NotificationCreateSchema(
                user_id=transaction.user_id,
                roles=["USER", "LECTURER"],
                title="Nạp tiền thành công 💰",
                content=f"Bạn đã nạp {amount:,} VND vào ví thành công.",
                url="/wallets/transactions",
                type="wallet",
                role_target=["USER", "LECTURER"],
                metadata={"transaction_id": str(transaction.id)},
                action="open_url",
            )
        )

        # ========================
        # 9) NOTIFY ADMIN
        # ========================
        await notification_service.create_notification_async(
            NotificationCreateSchema(
                user_id=None,
                roles=["ADMIN"],
                title="Có giao dịch nạp tiền mới 💵",
                content=f"Người dùng {user.fullname if user else transaction.user_id} vừa nạp {amount:,} VND qua PayPal.",
                url="/admin/wallets",
                type="platform_wallet",
                role_target=["ADMIN"],
                metadata={"transaction_id": str(transaction.id)},
                action="open_url",
            )
        )

        # ========================
        # 10) COMMIT
        # ========================
        await self.db.commit()

        # ========================
        # 11) REDIRECT FE
        # ========================
        redirect_url = self._payment_redirect_url(transaction, "success", token)

        return RedirectResponse(url=redirect_url)

    async def paypal_cancel_async(self, token: str):
        try:
            if not token:
                raise HTTPException(status_code=400, detail="Thiếu token (order_id).")

            # 🔍 Lấy transaction theo order_id
            query = await self.db.execute(
                select(Transactions).where(Transactions.order_id == token)
            )
            transaction: Transactions | None = query.scalar_one_or_none()
            if not transaction:
                raise HTTPException(
                    status_code=404, detail="Không tìm thấy giao dịch trong hệ thống."
                )

            # ⚠️ Nếu giao dịch đã completed thì bỏ qua
            if transaction.status == "completed":
                redirect_url = self._payment_redirect_url(transaction, "success", token)
                return RedirectResponse(url=redirect_url)

            # ❌ Đánh dấu giao dịch thất bại / bị hủy
            transaction.status = "canceled"
            transaction.confirmed_at = await to_utc_naive(get_now())
            transaction.description = (
                transaction.description or ""
            ) + " (Người dùng hủy trên PayPal)"

            await self.db.commit()

            # 🔁 Redirect về FE
            redirect_url = self._payment_redirect_url(transaction, "failed", token)
            return RedirectResponse(url=redirect_url)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi hủy thanh toán: {e}")

    async def get_by_user_id(self, user_id):
        try:
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == user_id)
            )
            return wallet
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi lấy ví: {e}")

    async def get_or_create_wallet_async(self, user_id: uuid.UUID):
        """Lấy ví của user, nếu chưa có thì tạo mới."""
        wallet = await self.db.scalar(
            select(Wallets).where(Wallets.user_id == user_id)
        )
        if not wallet:
            wallet = Wallets(
                user_id=user_id,
                balance=Decimal(0),
                currency="VND",
                total_in=Decimal(0),
                total_out=Decimal(0),
                created_at=await to_utc_naive(get_now()),
                updated_at=await to_utc_naive(get_now()),
            )
            self.db.add(wallet)
            # Lưu ý: Không commit ở đây để dùng chung transaction với service gọi nó
            await self.db.flush()
        return wallet

    async def retry_wallet_payment_async(self, http, order_id: str, user_id: uuid.UUID):
        try:
            tran: Transactions | None = await self.db.scalar(
                select(Transactions).where(
                    Transactions.order_id == order_id,
                    Transactions.status == "pending",
                    Transactions.method == "paypal",
                    Transactions.user_id == user_id,
                )
            )
            if not tran:
                raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch.")

            # 🔒 Kiểm tra trạng thái
            if tran.status != "pending":
                raise HTTPException(
                    status_code=400,
                    detail="Giao dịch không còn ở trạng thái chờ thanh toán.",
                )

            # ⏱ Kiểm tra thời hạn 3h
            expired_time = (
                tran.created_at + timedelta(hours=3) if tran.created_at else None
            )
            if expired_time and get_now() > expired_time:
                tran.status = "failed"
                tran.description = (
                    "Giao dịch đã bị hủy do dệ thống, do quá hạn thời gian."
                )
                await self.db.commit()
                raise HTTPException(
                    status_code=400,
                    detail="Đơn hàng PayPal đã hết hạn, vui lòng tạo thanh toán mới.",
                )

            paypal = PayPalService(http)
            result = await paypal.get_order_detail(order_id)
            status = result.get("status")

            # 🔗 Lấy lại link approve nếu còn hiệu lực
            approve_link = next(
                (
                    link["href"]
                    for link in result.get("links", [])
                    if link["rel"] == "approve"
                ),
                None,
            )

            if not approve_link:
                tran.status = "failed"
                tran.description = "Không tìm thấy liên kết thanh toán hoặc order đã bị hủy bởi hệ thốnng do quá hạn thời gian."
                await self.db.commit()
                raise HTTPException(
                    status_code=400,
                    detail="Không tìm thấy liên kết thanh toán hoặc order đã bị hủy.",
                )

            # 💲 Quy đổi lại số tiền để hiển thị cho FE
            usd_value = await convert_vnd_to_usd(float(tran.amount))
            usd_str = f"{usd_value:.2f}"
            return {
                "order_id": order_id,
                "status": status,
                "amount_vnd": str(tran.amount),
                "amount_usd": usd_str,
                "approve_url": approve_link,
                "user_id": str(tran.user_id),
                "can_retry": True,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi tạo lại thanh toán: {e}"
            )

    async def ensure_wallet_balance(self, user_id: uuid.UUID, required_amount: Decimal):
        """
        Kiểm tra số dư ví có đủ để giao dịch hay không.
        - required_amount: số tiền cần giao dịch (Decimal)
        - Nếu không đủ → bắn HTTPException 400
        """

        wallet = await self.db.scalar(select(Wallets).where(Wallets.user_id == user_id))

        if wallet is None:
            raise HTTPException(status_code=404, detail="Ví không tồn tại.")

        balance = wallet.balance or Decimal(0)

        if required_amount > balance:
            raise HTTPException(
                status_code=400,
                detail=f"Số dư không đủ. Cần {required_amount:,} VND nhưng ví chỉ có {balance:,} VND.",
            )

        return True
