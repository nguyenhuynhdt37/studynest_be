import uuid
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import (
    Courses,
    DiscountHistory,
    Discounts,
    InstructorEarnings,
    PlatformWalletHistory,
    PlatformWallets,
    PurchaseItems,
    Transactions,
    User,
)
from app.db.sesson import get_session


class PlatformWalletService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_platform_wallet_with_recent_history(self):
        # 1) Lấy ví nền tảng (chỉ có 1 ví)
        wallet = await self.db.scalar(
            select(PlatformWallets).order_by(PlatformWallets.updated_at.desc()).limit(1)
        )

        if not wallet:
            raise HTTPException(404, "Ví nền tảng chưa được khởi tạo.")

        # 2) Lấy top 5 lịch sử gần nhất
        history = (
            (
                await self.db.execute(
                    select(PlatformWalletHistory)
                    .where(PlatformWalletHistory.wallet_id == wallet.id)
                    .order_by(PlatformWalletHistory.created_at.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

        # 3) Trả response chuẩn
        return {
            "wallet": {
                "id": str(wallet.id),
                "balance": float(wallet.balance),
                "total_in": float(wallet.total_in),
                "total_out": float(wallet.total_out),
                "holding_amount": float(wallet.holding_amount),
                "platform_fee_total": float(wallet.platform_fee_total),
                "currency": wallet.currency,
                "updated_at": wallet.updated_at,
            },
            "recent_history": [
                {
                    "id": str(h.id),
                    "type": h.type,
                    "amount": float(h.amount),
                    "note": h.note,
                    "related_transaction_id": (
                        str(h.related_transaction_id)
                        if h.related_transaction_id
                        else None
                    ),
                    "created_at": h.created_at,
                }
                for h in history
            ],
        }

    async def get_platform_wallet_transaction_detail_admin_async(
        self, history_id: uuid.UUID
    ):
        # 1) Lấy log ví
        log = await self.db.scalar(
            select(PlatformWalletHistory).where(PlatformWalletHistory.id == history_id)
        )
        if not log:
            raise HTTPException(404, "Không tìm thấy giao dịch ví hệ thống.")

        # 2) Lấy ví hệ thống
        wallet = await self.db.scalar(
            select(PlatformWallets).where(PlatformWallets.id == log.wallet_id)
        )

        # 3) Lấy transaction gốc
        tx = None
        if log.related_transaction_id:
            tx = await self.db.scalar(
                select(Transactions).where(
                    Transactions.id == log.related_transaction_id
                )
            )

        user = None
        courses = []
        purchase_items = []
        instructor_earnings = []
        discount_history = []
        discount_info = None

        if tx:
            # User
            user = await self.db.scalar(select(User).where(User.id == tx.user_id))

            # Purchase Items
            purchase_items = (
                (
                    await self.db.execute(
                        select(PurchaseItems).where(
                            PurchaseItems.transaction_id == tx.id
                        )
                    )
                )
                .scalars()
                .all()
            )

            # Courses multi
            course_ids = [pi.course_id for pi in purchase_items]
            if course_ids:
                courses = (
                    (
                        await self.db.execute(
                            select(Courses).where(Courses.id.in_(course_ids))
                        )
                    )
                    .scalars()
                    .all()
                )

            # Instructor Earnings
            instructor_earnings = (
                (
                    await self.db.execute(
                        select(InstructorEarnings).where(
                            InstructorEarnings.transaction_id == tx.id
                        )
                    )
                )
                .scalars()
                .all()
            )

            # DiscountHistory
            purchase_item_ids = [pi.id for pi in purchase_items]
            if purchase_item_ids:
                discount_history = (
                    (
                        await self.db.execute(
                            select(DiscountHistory).where(
                                DiscountHistory.purchase_item_id.in_(purchase_item_ids)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                # Nếu có discount → lấy thông tin discount gốc
                if discount_history:
                    discount_id = discount_history[0].discount_id
                    discount_info = await self.db.scalar(
                        select(Discounts).where(Discounts.id == discount_id)
                    )

        # ======== Convert truyền thống ========
        def dt(x):
            return x.isoformat() if x else None

        # Log
        log_dict = {
            "id": str(log.id),
            "wallet_id": str(log.wallet_id),
            "type": log.type,
            "amount": float(log.amount),
            "note": log.note,
            "related_transaction_id": (
                str(log.related_transaction_id) if log.related_transaction_id else None
            ),
            "created_at": dt(log.created_at),
        }

        # Wallet
        wallet_dict = {
            "id": str(wallet.id),
            "balance": float(wallet.balance or 0),
            "total_in": float(wallet.total_in or 0),
            "total_out": float(wallet.total_out or 0),
            "holding_amount": float(wallet.holding_amount or 0),
            "platform_fee_total": float(wallet.platform_fee_total or 0),
            "currency": wallet.currency,
            "updated_at": dt(wallet.updated_at),
        }

        # Transaction
        tx_dict = None
        if tx:
            tx_dict = {
                "id": str(tx.id),
                "user_id": str(tx.user_id),
                "course_id": str(tx.course_id) if tx.course_id else None,
                "amount": float(tx.amount),
                "type": tx.type,
                "currency": tx.currency,
                "direction": tx.direction,
                "method": tx.method,
                "gateway": tx.gateway,
                "order_id": tx.order_id,
                "status": tx.status,
                "transaction_code": tx.transaction_code,
                "description": tx.description,
                "created_at": dt(tx.created_at),
                "confirmed_at": dt(tx.confirmed_at),
            }

        # User
        user_dict = None
        if user:
            user_dict = {
                "id": str(user.id),
                "fullname": user.fullname,
                "email": user.email,
                "avatar": user.avatar,
                "created_at": dt(user.create_at),
            }

        # Courses
        courses_dict = [
            {
                "id": str(c.id),
                "title": c.title,
                "base_price": float(c.base_price or 0),
                "thumbnail_url": c.thumbnail_url,
                "instructor_id": str(c.instructor_id),
            }
            for c in courses
        ]

        # PurchaseItems
        purchase_items_dict = [
            {
                "id": str(pi.id),
                "course_id": str(pi.course_id),
                "original_price": float(pi.original_price),
                "discounted_price": float(pi.discounted_price),
                "discount_amount": float(pi.discount_amount or 0),
                "discount_id": str(pi.discount_id) if pi.discount_id else None,
                "status": pi.status,
                "created_at": dt(pi.created_at),
            }
            for pi in purchase_items
        ]

        # Earnings
        earnings_dict = [
            {
                "id": str(e.id),
                "instructor_id": str(e.instructor_id),
                "amount_instructor": float(e.amount_instructor),
                "amount_platform": float(e.amount_platform),
                "status": e.status,
                "hold_until": dt(e.hold_until),
                "created_at": dt(e.created_at),
            }
            for e in instructor_earnings
        ]

        # DiscountHistory
        discount_history_dict = [
            {
                "id": str(d.id),
                "user_id": str(d.user_id),
                "discount_id": str(d.discount_id),
                "purchase_item_id": str(d.purchase_item_id),
                "discounted_amount": float(d.discounted_amount),
                "created_at": dt(d.created_at),
            }
            for d in discount_history
        ]

        # Discount Info (nếu có)
        discount_dict = None
        if discount_info:
            discount_dict = {
                "id": str(discount_info.id),
                "name": discount_info.name,
                "discount_code": discount_info.discount_code,
                "applies_to": discount_info.applies_to,
                "discount_type": discount_info.discount_type,
                "percent_value": float(discount_info.percent_value or 0),
                "fixed_value": float(discount_info.fixed_value or 0),
                "usage_limit": discount_info.usage_limit,
                "usage_count": discount_info.usage_count,
                "start_at": dt(discount_info.start_at),
                "end_at": dt(discount_info.end_at),
            }

        return {
            "log": log_dict,
            "wallet": wallet_dict,
            "transaction": tx_dict,
            "user": user_dict,
            "courses": courses_dict,
            "purchase_items": purchase_items_dict,
            "instructor_earnings": earnings_dict,
            "discount_history": discount_history_dict,
            "discount": discount_dict,
        }

    async def get_platform_wallet_history_admin_async(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        type_: Optional[str] = None,  # in / out / hold / release / fee / refund
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        transaction_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        order_dir: str = "desc",
    ):

        # Sort an toàn
        valid_sort_fields = {
            "amount": PlatformWalletHistory.amount,
            "type": PlatformWalletHistory.type,
            "created_at": PlatformWalletHistory.created_at,
        }

        sort_field = valid_sort_fields.get(sort_by, PlatformWalletHistory.created_at)
        sort_order = (
            sort_field.desc() if order_dir.lower() == "desc" else sort_field.asc()
        )

        # Base query
        base_stmt = select(PlatformWalletHistory)

        # ============================
        # FILTER
        # ============================
        filters = []

        if type_:
            filters.append(PlatformWalletHistory.type == type_)

        if transaction_id:
            filters.append(
                PlatformWalletHistory.related_transaction_id == transaction_id
            )

        if date_from:
            filters.append(PlatformWalletHistory.created_at >= date_from)

        if date_to:
            filters.append(PlatformWalletHistory.created_at <= date_to)

        if search:
            kw = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(PlatformWalletHistory.note).ilike(kw),
                )
            )

        if filters:
            base_stmt = base_stmt.where(and_(*filters))

        # ============================
        # TOTAL COUNT
        # ============================
        total = (
            await self.db.execute(
                select(func.count()).select_from(base_stmt.subquery())
            )
        ).scalar_one()

        # ============================
        # PAGINATION
        # ============================
        offset = (page - 1) * limit
        stmt = base_stmt.order_by(sort_order).limit(limit).offset(offset)

        items = (await self.db.execute(stmt)).scalars().all()
        return {"total": total, "page": page, "limit": limit, "items": items}
