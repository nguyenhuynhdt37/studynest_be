from datetime import datetime
from operator import or_

from fastapi import Depends, HTTPException
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import (
    PlatformSettings,
    Transactions,
    User,
    Wallets,
    WithdrawalRequests,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now
from app.schemas.shares.notification import NotificationCreateSchema
from app.services.shares.notification import NotificationService


class WithdrawService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    # ============================================================
    # LIST REQUESTS
    # ============================================================
    async def list_withdraw_requests(
        self,
        user: User,
        role: str,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
        amount_min: float | None = None,
        amount_max: float | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        order_by: str = "requested_at",
        order_dir: str = "desc",
    ):
        try:
            offset = (page - 1) * limit

            # MAP SORT
            valid_sort = {
                "requested_at": WithdrawalRequests.requested_at,
                "amount": WithdrawalRequests.amount,
                "status": WithdrawalRequests.status,
            }
            sort_field = valid_sort.get(order_by, WithdrawalRequests.requested_at)
            sort_order = desc(sort_field) if order_dir == "desc" else asc(sort_field)

            # BASE QUERY
            query = select(
                WithdrawalRequests,
                User.id.label("lecturer_id"),
                User.fullname.label("lecturer_name"),
                User.email.label("lecturer_email"),
                User.avatar.label("lecturer_avatar"),
                User.bio.label("lecturer_bio"),
            ).join(User, User.id == WithdrawalRequests.lecturer_id)

            # ROLE FILTER
            if role == "LECTURER":
                query = query.where(WithdrawalRequests.lecturer_id == user.id)

            elif role == "ADMIN":
                if status:
                    query = query.where(WithdrawalRequests.status == status)

            # SEARCH
            if search:
                s = f"%{search}%"
                query = query.where(or_(User.fullname.ilike(s), User.email.ilike(s)))

            # AMOUNT RANGE
            if amount_min is not None:
                query = query.where(WithdrawalRequests.amount >= amount_min)

            if amount_max is not None:
                query = query.where(WithdrawalRequests.amount <= amount_max)

            # DATE RANGE
            if date_from:
                query = query.where(WithdrawalRequests.requested_at >= date_from)

            if date_to:
                query = query.where(WithdrawalRequests.requested_at <= date_to)

            # APPLY SORT
            query = query.order_by(sort_order)

            # TOTAL COUNT
            total = await self.db.scalar(
                select(func.count()).select_from(query.subquery())
            )

            # FETCH
            rows = await self.db.execute(query.offset(offset).limit(limit))
            rows = rows.fetchall()

            data = []
            for r in rows:
                withdraw, lecturer_id, name, email, avatar, bio = r
                data.append(
                    {
                        "id": str(withdraw.id),
                        "amount": float(withdraw.amount),
                        "currency": withdraw.currency,
                        "status": withdraw.status,
                        "requested_at": withdraw.requested_at,
                        "approved_at": withdraw.approved_at,
                        "paypal_batch_id": withdraw.paypal_batch_id,
                        "lecturer": {
                            "id": str(lecturer_id),
                            "fullname": name,
                            "email": email,
                            "avatar": avatar,
                            "bio": bio,
                        },
                    }
                )

            return {
                "page": page,
                "limit": limit,
                "total": total,
                "data": data,
            }

        except HTTPException:
            raise

        except Exception as e:
            print("❌ Error in list_withdraw_requests:", e)
            raise HTTPException(500, "Lỗi hệ thống khi lấy danh sách rút tiền.")

    # ============================================================
    # REQUEST WITHDRAW
    # ============================================================
    async def request_withdraw_async(
        self,
        lecturer: User,
        amount: float,
        notification_service: NotificationService,
    ):
        try:
            if amount <= 0:
                raise HTTPException(400, "Số tiền rút không hợp lệ.")

            # WALLET
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == lecturer.id)
            )
            if wallet is None:
                raise HTTPException(404, "Không tìm thấy ví giảng viên.")

            # SETTINGS
            settings = await self.db.scalar(select(PlatformSettings))
            if settings is None:
                raise HTTPException(500, "Thiếu cấu hình nền tảng.")

            minimum = float(settings.payout_min_balance or 100000)

            if amount < minimum:
                raise HTTPException(
                    400,
                    f"Số tiền rút tối thiểu là {minimum:,.0f} {settings.currency}.",
                )

            if float(wallet.balance or 0) < amount:
                raise HTTPException(400, "Số dư trong ví không đủ để rút tiền.")

            # TRANSACTION ATOMIC
            async with self.db.begin():

                # 1) Tạo Withdrawal Request
                withdraw = WithdrawalRequests(
                    lecturer_id=lecturer.id,
                    amount=amount,
                    currency="VND",
                    status="pending",
                    requested_at=now(),
                )
                self.db.add(withdraw)
                await self.db.flush()

                # 2) Transaction pending
                txn = Transactions(
                    user_id=lecturer.id,
                    amount=amount,
                    type="withdraw_request",
                    direction="out",
                    status="pending",
                    method="wallet",
                    gateway="internal",
                    currency=settings.currency,
                    ref_id=withdraw.id,
                    description=f"Yêu cầu rút {amount:,.0f} {settings.currency}.",
                    created_at=now(),
                )
                self.db.add(txn)
                await self.db.flush()

            # 3) Notify ADMIN
            await notification_service.create_notification_async(
                NotificationCreateSchema(
                    user_id=None,
                    roles=["ADMIN"],
                    title="Có yêu cầu rút tiền mới 💸",
                    content=(
                        f"Giảng viên {lecturer.fullname} vừa yêu cầu rút "
                        f"{amount:,.0f} {settings.currency}."
                    ),
                    url="/admin/wallet/withdraw-requests",
                    type="withdraw_request",
                    role_target=["ADMIN"],
                    metadata={
                        "withdrawal_id": str(withdraw.id),
                        "transaction_id": str(txn.id),
                    },
                    action="open_url",
                )
            )

            # 4) Notify LECTURER
            await notification_service.create_notification_async(
                NotificationCreateSchema(
                    user_id=lecturer.id,
                    roles=["LECTURER"],
                    title="Yêu cầu rút tiền đã được tạo",
                    content=(
                        f"Bạn đã yêu cầu rút {amount:,.0f} {settings.currency}. "
                        "Hệ thống sẽ xử lý sau khi admin duyệt."
                    ),
                    url="/lecturer/wallet/withdraw-history",
                    type="wallet",
                    role_target=["LECTURER"],
                    metadata={"withdrawal_id": str(withdraw.id)},
                    action="open_url",
                )
            )

            return {
                "message": "Yêu cầu rút tiền đã được tạo.",
                "request_id": str(withdraw.id),
                "amount": amount,
                "currency": settings.currency,
            }

        except HTTPException:
            raise

        except Exception as e:
            print("❌ Error in request_withdraw_async:", e)
            raise HTTPException(500, "Lỗi hệ thống khi tạo yêu cầu rút tiền.")
