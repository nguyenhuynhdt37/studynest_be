import datetime
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy import String, and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthorizationService
from app.db.models.database import (
    CourseEnrollments,
    Courses,
    DiscountHistory,
    Discounts,
    InstructorEarnings,
    PlatformSettings,
    PlatformWalletHistory,
    PurchaseItems,
    RefundRequests,
    Transactions,
    User,
    Wallets,
    WithdrawalRequests,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_vietnam_naive
from app.schemas.shares.notification import NotificationCreateSchema
from app.services.shares.discounts import DiscountService
from app.services.shares.notification import NotificationService
from app.services.shares.wallets import WalletsService

MAX_PENDING_HOURS = 3


class TransactionsService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_user_transactions(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
        status: str | None = None,
        type_: str | None = None,  # deposit | purchase | refund | withdraw
        method: str | None = None,  # paypal | momo | internal
        order_by: str = "created_at",
        order_dir: str = "desc",
        date_from: Optional[datetime.datetime] = None,
        date_to: Optional[datetime.datetime] = None,
    ):
        """
        Lấy danh sách giao dịch của người dùng.
        Chuẩn hóa để phục vụ tính năng hoàn tiền sau này.
        """

        now = get_now()

        # ====================================================
        # 1) TỰ ĐỘNG HỦY GIAO DỊCH pending QUÁ 3 GIỜ
        # ====================================================
        expire_time = now - timedelta(hours=3)

        await self.db.execute(
            update(Transactions)
            .where(Transactions.user_id == user_id)
            .where(Transactions.status == "pending")
            .where(Transactions.created_at < expire_time)
            .values(
                status="canceled",
                confirmed_at=now,
                description=func.concat(
                    Transactions.description,
                    " (Tự động hủy do quá hạn thanh toán)",
                ),
            )
        )
        await self.db.commit()

        # ====================================================
        # 2) QUERY CHÍNH
        # ====================================================
        query = select(Transactions).where(Transactions.user_id == user_id)

        # ----- SEARCH -----
        if search:
            s = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(Transactions.description).like(s),
                    func.lower(Transactions.transaction_code).like(s),
                    func.lower(Transactions.order_id.cast(String)).like(s),
                )
            )

        # ----- LỌC THEO TRẠNG THÁI -----
        if status:
            query = query.where(Transactions.status == status)

        # ----- LỌC THEO LOẠI (purchase, deposit, withdraw, refund) -----
        if type_:
            query = query.where(Transactions.type == type_)

        # ----- LỌC PAYMENT METHOD (paypal/momo/bank...) -----
        if method:
            query = query.where(func.lower(Transactions.method) == method.lower())

        # ----- LỌC NGÀY -----
        if date_from and date_to:
            query = query.where(Transactions.created_at.between(date_from, date_to))

        # ====================================================
        # 3) SẮP XẾP
        # ====================================================
        order_column = getattr(Transactions, order_by, Transactions.created_at)
        if order_dir.lower() == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # ====================================================
        # 4) PHÂN TRANG
        # ====================================================
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # ====================================================
        # 5) FETCH DATA
        # ====================================================
        result = await self.db.execute(query)
        items = result.scalars().all()

        # ====================================================
        # 6) TÍNH TOTAL
        # ====================================================
        total_query = (
            select(func.count())
            .select_from(Transactions)
            .where(Transactions.user_id == user_id)
        )

        if search:
            total_query = total_query.where(
                or_(
                    func.lower(Transactions.description).like(s),
                    func.lower(Transactions.transaction_code).like(s),
                )
            )
        if status:
            total_query = total_query.where(Transactions.status == status)
        if type_:
            total_query = total_query.where(Transactions.type == type_)
        if method:
            total_query = total_query.where(
                func.lower(Transactions.method) == method.lower()
            )

        total = (await self.db.execute(total_query)).scalar() or 0

        # ====================================================
        # 7) RETURN — chuẩn UI
        # ====================================================
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "transactions": [
                {
                    "id": str(t.id),
                    "type": t.type,  # purchase / deposit / refund / withdraw
                    "method": t.method,  # paypal / momo / internal
                    "gateway": t.gateway,  # paypal / momo
                    "amount": float(t.amount),
                    "direction": t.direction,
                    "currency": t.currency,
                    "status": t.status,  # pending / completed / canceled / refunded
                    "description": t.description,
                    "transaction_code": t.transaction_code,
                    "order_id": t.order_id,
                    "created_at": t.created_at,
                    "confirmed_at": t.confirmed_at,
                }
                for t in items
            ],
        }

    async def get_user_transaction_detail(
        self,
        transaction_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """
        Lấy chi tiết 1 giao dịch (tự động phân loại):
        - deposit
        - purchase
        - refund
        - income
        - withdraw_request
        - withdraw_paid
        """

        tx = await self.db.scalar(
            select(Transactions)
            .where(Transactions.id == transaction_id)
            .where(Transactions.user_id == user_id)
        )

        if not tx:
            raise HTTPException(404, "Không tìm thấy giao dịch.")

        detail = {
            "id": str(tx.id),
            "type": tx.type,
            "direction": tx.direction,
            "amount": float(tx.amount),
            "currency": tx.currency,
            "gateway": tx.gateway,
            "method": tx.method,
            "status": tx.status,
            "description": tx.description,
            "transaction_code": tx.transaction_code,
            "order_id": tx.order_id,
            "created_at": tx.created_at,
            "confirmed_at": tx.confirmed_at,
        }

        # =====================================================
        # NHÓM 1: GIAO DỊCH NẠP TIỀN PAYPAL (deposit)
        # =====================================================
        if tx.type == "deposit":
            detail["deposit"] = {
                "paypal_order_id": tx.order_id,
                "paypal_capture_id": tx.transaction_code,
                "from": tx.gateway,
            }
            return detail

        # =====================================================
        # NHÓM 2: GIAO DỊCH MUA KHÓA HỌC (purchase)
        # =====================================================
        if tx.type == "purchase":
            purchase_item = await self.db.scalar(
                select(PurchaseItems).where(PurchaseItems.transaction_id == tx.id)
            )
            if purchase_item:
                detail["purchase"] = {
                    "purchase_item_id": str(purchase_item.id),
                    "original_price": float(purchase_item.original_price),
                    "discounted_price": float(purchase_item.discounted_price),
                    "discount_amount": float(purchase_item.discount_amount or 0),
                    "status": purchase_item.status,
                }

                course = await self.db.scalar(
                    select(Courses).where(Courses.id == purchase_item.course_id)
                )
                if course:
                    detail["course"] = {
                        "id": str(course.id),
                        "title": course.title,
                        "slug": course.slug,
                        "thumbnail": course.thumbnail_url,
                        "instructor_id": str(course.instructor_id),
                    }

                discount = None
                if purchase_item.discount_id:
                    discount = await self.db.scalar(
                        select(Discounts).where(
                            Discounts.id == purchase_item.discount_id
                        )
                    )
                if discount:
                    detail["discount"] = {
                        "code": discount.discount_code,
                        "type": discount.discount_type,
                        "percent_value": float(discount.percent_value or 0),
                        "fixed_value": float(discount.fixed_value or 0),
                    }

                refund_request = await self.db.scalar(
                    select(RefundRequests).where(
                        RefundRequests.purchase_item_id == purchase_item.id
                    )
                )
                if refund_request:
                    detail["refund_request"] = {
                        "refund_id": str(refund_request.id),
                        "status": refund_request.status,
                        "amount": float(refund_request.refund_amount),
                    }

            return detail

        # =====================================================
        # NHÓM 3: THU NHẬP GIẢNG VIÊN (income)
        # =====================================================
        if tx.type == "income":
            earning = await self.db.scalar(
                select(InstructorEarnings).where(
                    InstructorEarnings.transaction_id == tx.id
                )
            )
            if earning:
                detail["income"] = {
                    "amount_instructor": float(earning.amount_instructor),
                    "amount_platform": float(earning.amount_platform),
                    "hold_until": earning.hold_until,
                    "available_at": earning.available_at,
                    "paid_at": earning.paid_at,
                }
            return detail

        # =====================================================
        # NHÓM 4: HOÀN TIỀN (refund)
        # =====================================================
        if tx.type == "refund":
            refund = await self.db.scalar(
                select(RefundRequests).where(RefundRequests.id == tx.ref_id)
            )
            if refund:
                detail["refund"] = {
                    "refund_id": str(refund.id),
                    "status": refund.status,
                    "reason": refund.reason,
                    "refund_amount": float(refund.refund_amount),
                }
            return detail

        # =====================================================
        # NHÓM 5: RÚT TIỀN (withdraw_request / withdraw_paid)
        # =====================================================
        if tx.type.startswith("withdraw"):
            withdrawal = await self.db.scalar(
                select(WithdrawalRequests).where(WithdrawalRequests.id == tx.ref_id)
            )
            if withdrawal:
                detail["withdraw"] = {
                    "withdrawal_id": str(withdrawal.id),
                    "status": withdrawal.status,
                    "requested_at": withdrawal.requested_at,
                    "approved_at": withdrawal.approved_at,
                    "rejected_at": withdrawal.rejected_at,
                    "amount": float(withdrawal.amount),
                    "currency": withdrawal.currency,
                }
            return detail

        return detail

    async def checkout_wallet_async(
        self,
        user: User,
        course_ids: list[uuid.UUID],
        discount_code: str | None,
        wallets_service: WalletsService,
        discount_service: DiscountService,
    ):
        try:
            # ============================
            # 0) VALIDATE COURSE
            # ============================
            courses = (
                (
                    await self.db.execute(
                        select(Courses).where(Courses.id.in_(course_ids))
                    )
                )
                .scalars()
                .all()
            )

            if not courses:
                raise HTTPException(400, "Không tìm thấy khóa học nào.")

            if len(courses) != len(course_ids):
                raise HTTPException(400, "Một hoặc nhiều khóa học không tồn tại.")

            for c in courses:
                price = Decimal(str(c.base_price or 0))
                if price <= 0:
                    raise HTTPException(
                        400,
                        f"Khóa học '{c.title}' có giá 0đ — không thể thanh toán.",
                    )

            # ============================
            # 1) TÍNH DISCOUNT
            # ============================
            discount_result = await discount_service.calculate_discount_apply(
                user_id=user.id,
                course_ids=course_ids,
                discount_input=discount_code or "",
            )

            # ÉP ÂM THÀNH 0
            for item in discount_result["items"]:
                base = Decimal(str(item["base_price"]))
                final = Decimal(str(item["final_price"]))

                if final < 0:
                    item["final_price"] = "0"
                    item["discounted_amount"] = str(base)

            total_price = sum(
                Decimal(str(item["final_price"])) for item in discount_result["items"]
            )
            if total_price < 0:
                total_price = Decimal("0")

            now = get_now()
            purchase_items: list[PurchaseItems] = []
            transaction: Transactions | None = None

            # ==================================================
            # CASE 1: FREE CHECKOUT (total_price == 0)
            # → Không transaction, không earnings, không platform_wallet
            # ==================================================
            if total_price == 0:
                async with self.db.begin_nested():
                    # PURCHASE_ITEMS giá 0
                    for item in discount_result["items"]:
                        base_price = Decimal(str(item["base_price"]))

                        pi = PurchaseItems(
                            id=uuid.uuid4(),
                            transaction_id=None,
                            user_id=user.id,
                            course_id=item["course_id"],
                            original_price=base_price,
                            discounted_price=Decimal("0"),
                            discount_amount=None,
                            discount_id=None,
                            status="completed",
                            course_snapshot={
                                "title": item["course_title"],
                                "base_price": float(base_price),
                                "final_price": float(0),
                            },
                            created_at=now,
                        )
                        self.db.add(pi)
                        purchase_items.append(pi)

                    # DiscountHistory vẫn có thể log nếu muốn theo dõi marketing
                    if discount_result["discount_id"]:
                        for item, pi in zip(discount_result["items"], purchase_items):
                            if item.get("applied"):
                                dh = DiscountHistory(
                                    id=uuid.uuid4(),
                                    user_id=user.id,
                                    purchase_item_id=pi.id,
                                    discount_id=discount_result["discount_id"],
                                    discounted_amount=pi.original_price,
                                    created_at=now,
                                )
                                self.db.add(dh)

                    # ENROLL + CẬP NHẬT THỐNG KÊ
                    for pi in purchase_items:
                        existed = await self.db.scalar(
                            select(CourseEnrollments).where(
                                CourseEnrollments.user_id == user.id,
                                CourseEnrollments.course_id == pi.course_id,
                            )
                        )
                        if not existed:
                            enroll = CourseEnrollments(
                                id=uuid.uuid4(),
                                user_id=user.id,
                                course_id=pi.course_id,
                                enrolled_at=now,
                                progress=Decimal("0"),
                            )
                            self.db.add(enroll)

                            # ✅ CẬP NHẬT COURSES.TOTAL_ENROLLS
                            course_to_update = await self.db.scalar(
                                select(Courses).where(Courses.id == pi.course_id)
                            )
                            if course_to_update:
                                course_to_update.total_enrolls = (
                                    course_to_update.total_enrolls or 0
                                ) + 1

                                # ✅ CẬP NHẬT USER.STUDENT_COUNT CHO INSTRUCTOR
                                # Chỉ tăng nếu user này chưa từng đăng ký bất kỳ khóa học nào của instructor
                                instructor = await self.db.scalar(
                                    select(User).where(User.id == course_to_update.instructor_id)
                                )
                                if instructor:
                                    # Kiểm tra xem user đã là học viên của instructor này chưa
                                    existing_enrollment_count = await self.db.scalar(
                                        select(func.count())
                                        .select_from(CourseEnrollments)
                                        .join(Courses, Courses.id == CourseEnrollments.course_id)
                                        .where(
                                            CourseEnrollments.user_id == user.id,
                                            Courses.instructor_id == instructor.id,
                                        )
                                    )
                                    # Nếu đây là lần đầu (count = 0), tăng student_count
                                    if existing_enrollment_count == 0:
                                        instructor.student_count = (
                                            instructor.student_count or 0
                                        ) + 1

                # NOTI (chỉ enroll, không ví)
                try:
                    notification_service = NotificationService(self.db)
                    roles = await AuthorizationService.get_list_role_in_user(user)

                    for course in courses:
                        await notification_service.create_notification_async(
                            NotificationCreateSchema(
                                user_id=user.id,
                                roles=roles,
                                title="Đăng ký khóa học thành công 🎉",
                                content=f"Bạn đã đăng ký khóa học '{course.title}' thành công.",
                                url=f"/courses/{course.id}",
                                type="course",
                                role_target=["USER"],
                                metadata={"course_id": str(course.id)},
                                action="open_url",
                            )
                        )

                        await notification_service.create_notification_async(
                            NotificationCreateSchema(
                                user_id=course.instructor_id,
                                roles=["LECTURER"],
                                title=f"Học viên mới đăng ký khóa học '{course.title}' 🎉",
                                content=f"Người dùng {user.fullname} ({user.email}) vừa đăng ký khóa học của bạn.",
                                url=f"/instructor/courses/{course.id}",
                                type="course",
                                role_target=["LECTURER"],
                                metadata={
                                    "course_id": str(course.id),
                                    "student_id": str(user.id),
                                },
                                action="open_url",
                            )
                        )
                except Exception as noti_err:
                    logger.exception(
                        f"[CHECKOUT FREE][NOTI] Lỗi gửi thông báo: {noti_err}"
                    )

                return {
                    "message": "Đăng ký khóa học thành công 🎉",
                    "is_free": True,
                    "transaction_id": None,
                    "total_paid": "0",
                    "items": [
                        {
                            "course_id": str(pi.course_id),
                            "price": "0",
                            "discount_amount": "0",
                            "applied_discount": False,
                        }
                        for pi in purchase_items
                    ],
                }

            # ==================================================
            # CASE 2: PAID CHECKOUT (total_price > 0)
            # ==================================================

            # 2) CHECK VÍ
            await wallets_service.ensure_wallet_balance(
                user.id, Decimal(str(total_price))
            )

            # 3) LẤY VÍ USER
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == user.id).with_for_update()
            )
            if wallet is None:
                raise HTTPException(404, "Ví không tồn tại.")

            # 4) PLATFORM SETTINGS
            settings = await self.db.scalar(select(PlatformSettings))
            platform_fee = Decimal(str(settings.platform_fee or 0.3))
            hold_days = int(settings.hold_days or 7)

            async with self.db.begin_nested():

                # 5.1 TRỪ VÍ + TRANSACTION
                wallet.balance -= total_price
                wallet.total_out = (wallet.total_out or Decimal("0")) + total_price
                wallet.last_transaction_at = now

                transaction = Transactions(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    amount=total_price,
                    type="purchase",
                    currency="VND",
                    direction="out",
                    method="wallet",
                    gateway="internal_wallet",
                    status="completed",
                    description=f"Mua {len(course_ids)} khóa học bằng ví nội bộ",
                    created_at=now,
                    confirmed_at=now,
                )
                self.db.add(transaction)
                await self.db.flush()

                # 5.3 PURCHASE ITEMS
                for item in discount_result["items"]:
                    base_price = Decimal(str(item["base_price"]))
                    final_price = Decimal(str(item["final_price"]))
                    applied = item.get("applied", False)
                    discount_amount = (
                        Decimal(str(item["discounted_amount"]))
                        if applied
                        else Decimal("0")
                    )

                    pi = PurchaseItems(
                        id=uuid.uuid4(),
                        transaction_id=transaction.id,
                        user_id=user.id,
                        course_id=item["course_id"],
                        original_price=base_price,
                        discounted_price=final_price,
                        discount_amount=(
                            discount_amount if discount_amount > 0 else None
                        ),
                        discount_id=(
                            discount_result["discount_id"] if applied else None
                        ),
                        status="completed",
                        course_snapshot={
                            "title": item["course_title"],
                            "base_price": float(base_price),
                            "final_price": float(final_price),
                        },
                        created_at=now,
                    )
                    self.db.add(pi)
                    purchase_items.append(pi)

                # 5.4 DISCOUNT HISTORY + USAGE COUNT
                if discount_result["discount_id"]:
                    discount_used = False

                    for item, pi in zip(discount_result["items"], purchase_items):
                        if item.get("applied") and pi.discount_amount:
                            discount_used = True
                            dh = DiscountHistory(
                                id=uuid.uuid4(),
                                user_id=user.id,
                                purchase_item_id=pi.id,
                                discount_id=discount_result["discount_id"],
                                discounted_amount=pi.discount_amount,
                                created_at=now,
                            )
                            self.db.add(dh)

                    if discount_used:
                        discount_obj = await self.db.scalar(
                            select(Discounts).where(
                                Discounts.id == discount_result["discount_id"]
                            )
                        )
                        if discount_obj:
                            discount_obj.usage_count = (
                                discount_obj.usage_count or 0
                            ) + 1
                            discount_obj.updated_at = now
                            self.db.add(discount_obj)

                # 5.5 ENROLL + CẬP NHẬT THỐNG KÊ
                for pi in purchase_items:
                    existed = await self.db.scalar(
                        select(CourseEnrollments).where(
                            CourseEnrollments.user_id == user.id,
                            CourseEnrollments.course_id == pi.course_id,
                        )
                    )
                    if not existed:
                        enroll = CourseEnrollments(
                            id=uuid.uuid4(),
                            user_id=user.id,
                            course_id=pi.course_id,
                            enrolled_at=now,
                            progress=Decimal("0"),
                        )
                        self.db.add(enroll)

                        # ✅ CẬP NHẬT COURSES.TOTAL_ENROLLS
                        course_to_update = await self.db.scalar(
                            select(Courses).where(Courses.id == pi.course_id)
                        )
                        if course_to_update:
                            course_to_update.total_enrolls = (
                                course_to_update.total_enrolls or 0
                            ) + 1

                            # ✅ CẬP NHẬT USER.STUDENT_COUNT CHO INSTRUCTOR
                            # Chỉ tăng nếu user này chưa từng đăng ký bất kỳ khóa học nào của instructor
                            instructor = await self.db.scalar(
                                select(User).where(User.id == course_to_update.instructor_id)
                            )
                            if instructor:
                                # Kiểm tra xem user đã là học viên của instructor này chưa
                                existing_enrollment_count = await self.db.scalar(
                                    select(func.count())
                                    .select_from(CourseEnrollments)
                                    .join(Courses, Courses.id == CourseEnrollments.course_id)
                                    .where(
                                        CourseEnrollments.user_id == user.id,
                                        Courses.instructor_id == instructor.id,
                                    )
                                )
                                # Nếu đây là lần đầu (count = 0), tăng student_count
                                if existing_enrollment_count == 0:
                                    instructor.student_count = (
                                        instructor.student_count or 0
                                    ) + 1

                # 5.6 EARNINGS + PLATFORM WALLET (chỉ với khóa có tiền > 0)
                for pi in purchase_items:
                    if pi.discounted_price <= 0:
                        continue  # khóa này không sinh doanh thu

                    course = await self.db.scalar(
                        select(Courses).where(Courses.id == pi.course_id)
                    )
                    if not course:
                        continue

                    instructor_id = course.instructor_id
                    instructor_share = pi.discounted_price * (
                        Decimal("1") - platform_fee
                    )
                    platform_share = pi.discounted_price * platform_fee

                    # Instructor earnings (holding)
                    earning = InstructorEarnings(
                        id=uuid.uuid4(),
                        transaction_id=transaction.id,
                        instructor_id=instructor_id,
                        amount_instructor=instructor_share,
                        amount_platform=platform_share,
                        status="holding",
                        hold_until=now + timedelta(days=hold_days),
                        purchase_snapshot={
                            "course_title": course.title,
                            "price_paid": float(pi.discounted_price),
                        },
                        created_at=now,
                    )
                    self.db.add(earning)

            # ============================
            # 6) NOTIFICATIONS
            # ============================
            try:
                notification_service = NotificationService(self.db)
                roles = await AuthorizationService.get_list_role_in_user(user)

                # Noti ví
                if transaction is not None:
                    await notification_service.create_notification_async(
                        NotificationCreateSchema(
                            user_id=transaction.user_id,
                            roles=roles,
                            title="Mua khóa học thành công 💰",
                            content=f"Bạn đã mua khóa học với tổng giá {transaction.amount:,} VND thành công.",
                            type="wallet",
                            role_target=["USER"],
                            metadata={"transaction_id": str(transaction.id)},
                            url="/my-learning",
                            action="open_url",
                        )
                    )

                # Noti enroll + giảng viên
                for course in courses:
                    await notification_service.create_notification_async(
                        NotificationCreateSchema(
                            user_id=user.id,
                            roles=roles,
                            title="Đăng ký khóa học thành công 🎉",
                            content=f"Bạn đã đăng ký khóa học '{course.title}' thành công.",
                            url="/my-learning",
                            type="course",
                            role_target=["USER"],
                            metadata={"course_id": str(course.id)},
                            action="open_url",
                        )
                    )
                    await notification_service.create_notification_async(
                        NotificationCreateSchema(
                            user_id=course.instructor_id,
                            roles=["LECTURER"],
                            title=f"Học viên mới đăng ký khóa học '{course.title}' 🎉",
                            content=f"Người dùng {user.fullname} ({user.email}) vừa đăng ký khóa học của bạn.",
                            url=f"/instructor/courses/{course.id}",
                            type="course",
                            role_target=["LECTURER"],
                            metadata={
                                "course_id": str(course.id),
                                "student_id": str(user.id),
                            },
                            action="open_url",
                        )
                    )

            except Exception as noti_err:
                logger.exception(f"[CHECKOUT PAID][NOTI] Lỗi gửi thông báo: {noti_err}")

            # ============================
            # 7) RETURN
            # ============================
            return {
                "message": "Thanh toán thành công 🎉",
                "is_free": False,
                "transaction_id": (str(transaction.id) if transaction else None),
                "total_paid": str(total_price),
                "items": [
                    {
                        "course_id": str(pi.course_id),
                        "price": str(pi.discounted_price),
                        "discount_amount": str(pi.discount_amount or 0),
                        "applied_discount": bool(pi.discount_amount),
                    }
                    for pi in purchase_items
                ],
            }

        except HTTPException:
            # cho HTTPException đi thẳng ra ngoài
            raise

        except Exception as e:
            logger.exception(f"[CHECKOUT][ERROR] {e}")
            await self.db.rollback()
            raise HTTPException(500, "Lỗi hệ thống khi thanh toán bằng ví.")

    async def get_transactions_admin_async(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        type_: Optional[str] = None,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        method: Optional[str] = None,
        gateway: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        course_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime.datetime] = None,
        date_to: Optional[datetime.datetime] = None,
        sort_by: str = "created_at",
        order_dir: str = "desc",
    ):
        """
        ADMIN: Lấy danh sách giao dịch (Transactions) đầy đủ:
        - Phân trang
        - Lọc theo type / status / direction / method / gateway / user_id / course_id / date range
        - Tìm kiếm theo: user.name, user.email, course.title, order_id, transaction_code
        - Có summary: total_amount, total_in, total_out (chỉ completed)
        """
        # Chuẩn hóa datetime về UTC+7 naive để tránh offset-aware vs offset-naive
        date_from = await to_vietnam_naive(date_from)
        date_to = await to_vietnam_naive(date_to)
        # Map field sort an toàn
        valid_sort_fields = {
            "amount": Transactions.amount,
            "created_at": Transactions.created_at,
            "status": Transactions.status,
            "type": Transactions.type,
            "method": Transactions.method,
            "gateway": Transactions.gateway,
        }
        sort_field = valid_sort_fields.get(sort_by, Transactions.created_at)
        sort_order = (
            sort_field.desc() if order_dir.lower() == "desc" else sort_field.asc()
        )

        # ============================
        # 1) BASE QUERY (JOIN user, course để search)
        # ============================
        base_stmt = (
            select(Transactions, User, Courses)
            .join(User, User.id == Transactions.user_id, isouter=True)
            .join(Courses, Courses.id == Transactions.course_id, isouter=True)
        )

        conditions = []

        # ============================
        # 2) FILTER CƠ BẢN
        # ============================
        if type_:
            conditions.append(Transactions.type == type_)

        if status:
            conditions.append(Transactions.status == status)

        if direction:
            conditions.append(Transactions.direction == direction)

        if method:
            conditions.append(Transactions.method == method)

        if gateway:
            conditions.append(Transactions.gateway == gateway)

        if user_id:
            conditions.append(Transactions.user_id == user_id)

        if course_id:
            conditions.append(Transactions.course_id == course_id)

        # ============================
        # 3) FILTER DATE RANGE
        # ============================
        if date_from:
            conditions.append(Transactions.created_at >= date_from)

        if date_to:
            conditions.append(Transactions.created_at <= date_to)

        # ============================
        # 4) SEARCH (user, course, order_id, transaction_code)
        # ============================
        if search:
            kw = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(User.fullname).ilike(kw),
                    func.lower(User.email).ilike(kw),
                    func.lower(Courses.title).ilike(kw),
                    func.lower(Transactions.order_id).ilike(kw),
                    func.lower(Transactions.transaction_code).ilike(kw),
                )
            )

        if conditions:
            base_stmt = base_stmt.where(and_(*conditions))

        # ============================
        # 5) TOTAL COUNT
        # ============================
        count_stmt = select(func.count()).select_from(
            select(Transactions.id)
            .join(User, User.id == Transactions.user_id, isouter=True)
            .join(Courses, Courses.id == Transactions.course_id, isouter=True)
            .where(and_(*conditions))
            if conditions
            else select(Transactions.id)
            .join(User, User.id == Transactions.user_id, isouter=True)
            .join(Courses, Courses.id == Transactions.course_id, isouter=True)
        )

        total = (await self.db.execute(count_stmt)).scalar_one()

        # ============================
        # 6) SUMMARY (total_amount, total_in, total_out)
        # ============================
        # chỉ tính các giao dịch completed
        summary_conditions = list(conditions)
        summary_conditions.append(Transactions.status == "completed")

        summary_stmt = (
            select(
                func.coalesce(func.sum(Transactions.amount), 0).label("total_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transactions.direction == "in", Transactions.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    0,
                ).label("total_in"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transactions.direction == "out", Transactions.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    0,
                ).label("total_out"),
            ).where(and_(*summary_conditions))
            if summary_conditions
            else select(
                func.coalesce(func.sum(Transactions.amount), 0).label("total_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transactions.direction == "in", Transactions.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    0,
                ).label("total_in"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transactions.direction == "out", Transactions.amount),
                            else_=Decimal("0"),
                        )
                    ),
                    0,
                ).label("total_out"),
            )
        )

        summary_row = (await self.db.execute(summary_stmt)).one()
        total_amount = Decimal(summary_row.total_amount or 0)
        total_in = Decimal(summary_row.total_in or 0)
        total_out = Decimal(summary_row.total_out or 0)

        # ============================
        # 7) PAGINATION
        # ============================
        offset = (page - 1) * limit
        items_stmt = base_stmt.order_by(sort_order).limit(limit).offset(offset)

        result = await self.db.execute(items_stmt)
        rows = result.all()

        items = []
        for tx, u, c in rows:
            items.append(
                {
                    "transaction": {
                        "id": str(tx.id),
                        "ref_id": tx.ref_id,
                        "direction": tx.direction,
                        "confirmed_at": (
                            tx.confirmed_at.isoformat() if tx.confirmed_at else None
                        ),
                        "user_id": str(tx.user_id) if tx.user_id else None,
                        "method": tx.method,
                        "updated_at": tx.updated_at.isoformat(),
                        "gateway": tx.gateway,
                        "return_pathname": tx.return_pathname,
                        "order_id": tx.order_id,
                        "return_origin": tx.return_origin,
                        "type": tx.type,
                        "status": tx.status,
                        "amount": float(tx.amount),
                        "course_id": str(tx.course_id) if tx.course_id else None,
                        "transaction_code": tx.transaction_code,
                        "description": tx.description,
                        "currency": tx.currency,
                        "created_at": tx.created_at.isoformat(),
                    },
                    "user": (
                        {
                            "id": str(u.id),
                            "fullname": u.fullname,
                            "email": u.email,
                            "avatar": u.avatar,
                        }
                        if u
                        else None
                    ),
                    "course": (
                        {
                            "id": str(c.id),
                            "title": c.title,
                        }
                        if c
                        else None
                    ),
                }
            )

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "summary": {
                "total_amount": str(total_amount),
                "total_in": str(total_in),
                "total_out": str(total_out),
            },
            "items": items,
        }

    async def get_transaction_detail_admin_async(self, transaction_id: uuid.UUID):
        # ============================
        # 1) Lấy giao dịch chính
        # ============================
        tx = await self.db.scalar(
            select(Transactions).where(Transactions.id == transaction_id)
        )
        if tx is None:
            raise HTTPException(404, "Không tìm thấy giao dịch.")

        # ============================
        # 2) Lấy user
        # ============================
        user = await self.db.scalar(select(User).where(User.id == tx.user_id))

        # ============================
        # 3) Lấy ví user
        # ============================
        wallet = None
        if user:
            wallet = await self.db.scalar(
                select(Wallets).where(Wallets.user_id == user.id)
            )

        # ============================
        # 4) Lấy 5 giao dịch gần nhất (trừ giao dịch hiện tại)
        # ============================
        recent_transactions = []
        if user:
            recent_transactions = (
                (
                    await self.db.execute(
                        select(Transactions)
                        .where(Transactions.user_id == user.id)
                        .where(Transactions.id != transaction_id)
                        .order_by(Transactions.created_at.desc())
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )

        # ============================
        # 5) Course (có thể None)
        # ============================
        course = None
        if tx.course_id:
            course = await self.db.scalar(
                select(Courses).where(Courses.id == tx.course_id)
            )

        # ============================
        # 6) PurchaseItems
        # ============================
        purchase_items = (
            (
                await self.db.execute(
                    select(PurchaseItems).where(PurchaseItems.transaction_id == tx.id)
                )
            )
            .scalars()
            .all()
        )

        # ============================
        # 7) DiscountHistory
        # ============================
        discount_history = []
        if purchase_items:
            discount_history = (
                (
                    await self.db.execute(
                        select(DiscountHistory)
                        .where(DiscountHistory.user_id == tx.user_id)
                        .where(
                            DiscountHistory.purchase_item_id.in_(
                                [pi.id for pi in purchase_items]
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        # ============================
        # 8) Instructor Earnings
        # ============================
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

        # ============================
        # 9) Platform Wallet Logs
        # ============================
        platform_logs = (
            (
                await self.db.execute(
                    select(PlatformWalletHistory)
                    .where(PlatformWalletHistory.related_transaction_id == tx.id)
                    .order_by(PlatformWalletHistory.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

        # ============================
        # 10) Trả về tất cả
        # ============================
        return {
            "transaction": tx,  # giao dịch hiện tại
            "user": user,  # user thực hiện giao dịch
            "wallet": wallet,  # ví user
            "recent_transactions": recent_transactions,  # 5 giao dịch gần nhất
            "course": course,  # khóa học nếu có
            "purchase_items": purchase_items,  # items trong giao dịch
            "discount_history": discount_history,  # lịch sử mã giảm
            "instructor_earnings": instructor_earnings,  # earnings giữ/hỗ trợ payout
            "platform_wallet_logs": platform_logs,  # log ví hệ thống
        }

    async def get_lecturer_transactions(
        self,
        instructor_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
        type_: str | None = None,
        date_from: datetime.datetime | None = None,
        date_to: datetime.datetime | None = None,
    ):
        """
        Lấy lịch sử thu nhập của giảng viên (FULL DETAIL):
        - transaction
        - earnings
        - purchase_items
        - course
        - student
        - discount + discount_history
        """

        # =============================
        # 1. Base query: giao dịch của GIẢNG VIÊN
        # =============================
        # earning_types = ["earning_release", "earning_payout", "earning_refund"]

        query = select(Transactions).where(
            Transactions.user_id == instructor_id,
            # Transactions.type.in_(earning_types),
        )

        # ----- Search -----
        if search:
            s = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(Transactions.description).like(s),
                    func.lower(Transactions.transaction_code).like(s),
                )
            )

        # ----- Filter by status -----
        if status:
            query = query.where(Transactions.status == status)

        # ----- Filter by type -----
        if type_:
            query = query.where(Transactions.type == type_)

        # ----- Date filter -----
        if date_from and date_to:
            query = query.where(Transactions.created_at.between(date_from, date_to))

        # ----- Sort -----
        query = query.order_by(Transactions.created_at.desc())

        # ----- Paging -----
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        rows = (await self.db.execute(query)).scalars().all()

        result = []

        # =============================
        # 2. Build FULL DETAIL cho từng transaction
        # =============================
        for tx in rows:
            # 2.1 Earnings (chỉ 1)
            earnings = await self.db.scalar(
                select(InstructorEarnings).where(
                    InstructorEarnings.transaction_id == tx.id
                )
            )

            purchase_items = []
            course = None
            student = None
            discount_history = []
            discount_info = None

            # 2.2 Lấy purchase_items từ giao dịch học viên (transaction_id gốc)
            if earnings and earnings.transaction_id:
                purchase_items = (
                    (
                        await self.db.execute(
                            select(PurchaseItems).where(
                                PurchaseItems.transaction_id == earnings.transaction_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                if purchase_items:
                    # ------ Course ------
                    course = await self.db.scalar(
                        select(Courses).where(Courses.id == purchase_items[0].course_id)
                    )

                    # ------ Student ------
                    student = await self.db.scalar(
                        select(User).where(User.id == purchase_items[0].user_id)
                    )

                    # ------ Discount History ------
                    pi_ids = [pi.id for pi in purchase_items]
                    discount_history = (
                        (
                            await self.db.execute(
                                select(DiscountHistory).where(
                                    DiscountHistory.purchase_item_id.in_(pi_ids)
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )

                    # ------ Discount Info ------
                    if discount_history:
                        discount_info = await self.db.scalar(
                            select(Discounts).where(
                                Discounts.id == discount_history[0].discount_id
                            )
                        )

            # =============================
            # 3. Convert THỦ CÔNG → dạng dict
            # =============================
            def dt(x):
                return x.isoformat() if x else None

            # --- transaction ---
            tx_dict = {
                "id": str(tx.id),
                "amount": float(tx.amount or 0),
                "type": tx.type,
                "status": tx.status,
                "description": tx.description,
                "gateway": tx.gateway,
                "direction": tx.direction,
                "method": tx.method,
                "transaction_code": tx.transaction_code,
                "order_id": tx.order_id,
                "created_at": dt(tx.created_at),
                "confirmed_at": dt(tx.confirmed_at),
            }

            # --- earnings ---
            earnings_dict = None
            if earnings:
                earnings_dict = {
                    "id": str(earnings.id),
                    "status": earnings.status,
                    "amount_instructor": float(earnings.amount_instructor),
                    "amount_platform": float(earnings.amount_platform),
                    "hold_until": dt(earnings.hold_until),
                    "available_at": dt(earnings.available_at),
                    "created_at": dt(earnings.created_at),
                    "purchase_snapshot": earnings.purchase_snapshot,
                }

            # --- course ---
            course_dict = None
            if course:
                course_dict = {
                    "id": str(course.id),
                    "title": course.title,
                    "thumbnail_url": course.thumbnail_url,
                    "base_price": float(course.base_price or 0),
                }

            # --- student ---
            student_dict = None
            if student:
                student_dict = {
                    "id": str(student.id),
                    "fullname": student.fullname,
                    "email": student.email,
                    "avatar": student.avatar,
                }

            # --- purchase items ---
            purchase_items_dict = [
                {
                    "id": str(pi.id),
                    "course_id": str(pi.course_id),
                    "original_price": float(pi.original_price),
                    "discounted_price": float(pi.discounted_price),
                    "discount_amount": float(pi.discount_amount or 0),
                    "status": pi.status,
                    "created_at": dt(pi.created_at),
                }
                for pi in purchase_items
            ]

            # --- discount history ---
            discount_history_dict = [
                {
                    "id": str(d.id),
                    "discount_id": str(d.discount_id),
                    "discounted_amount": float(d.discounted_amount),
                    "created_at": dt(d.created_at),
                }
                for d in discount_history
            ]

            # --- discount info ---
            discount_dict = None
            if discount_info:
                discount_dict = {
                    "id": str(discount_info.id),
                    "name": discount_info.name,
                    "discount_code": discount_info.discount_code,
                    "discount_type": discount_info.discount_type,
                    "percent_value": float(discount_info.percent_value or 0),
                    "fixed_value": float(discount_info.fixed_value or 0),
                    "start_at": dt(discount_info.start_at),
                    "end_at": dt(discount_info.end_at),
                }

            # ADD KẾT QUẢ
            result.append(
                {
                    "transaction": tx_dict,
                    "earnings": earnings_dict,
                    "course": course_dict,
                    "student": student_dict,
                    "purchase_items": purchase_items_dict,
                    "discount_history": discount_history_dict,
                    "discount": discount_dict,
                }
            )

        # =============================
        # 4. Total count
        # =============================
        total = (
            await self.db.execute(
                select(func.count()).where(
                    Transactions.user_id == instructor_id,
                    # Transactions.type.in_(earning_types),
                )
            )
        ).scalar()

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "items": result,
        }

    async def get_instructor_pending_earnings(
        self,
        instructor_id: uuid.UUID | None = None,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
        status: str | None = None,  # holding | freeze
        course_id: uuid.UUID | None = None,
        student_id: uuid.UUID | None = None,
        date_from: datetime.datetime | None = None,
        date_to: datetime.datetime | None = None,
        order_by: str = "hold_until",  # sort field
        order_dir: str = "asc",  # asc | desc
        role: str = "LECTURER",
    ):
        """
        Danh sách các khoản earnings đang chờ trả cho giảng viên.
        Bao gồm:
        - status = holding   → chờ trả
        - status = freeze    → bị đóng băng vì refund request

        Có phân trang + lọc + tìm kiếm + sắp xếp.
        """

        try:
            offset = (page - 1) * limit

            # ------------------------------------------------------
            # Field hợp lệ để sort
            # ------------------------------------------------------
            valid_sort_fields = {
                "created_at": InstructorEarnings.created_at,
                "hold_until": InstructorEarnings.hold_until,
                "amount_instructor": InstructorEarnings.amount_instructor,
                "status": InstructorEarnings.status,
            }

            sort_column = valid_sort_fields.get(order_by, InstructorEarnings.hold_until)
            sort_column = (
                sort_column.desc() if order_dir == "desc" else sort_column.asc()
            )

            # ------------------------------------------------------
            # Base query
            # ------------------------------------------------------
            if role == "ADMIN":
                query = (
                    select(
                        InstructorEarnings,
                        PurchaseItems,
                        Courses,
                        User,  # student
                        RefundRequests,
                    )
                    .join(
                        PurchaseItems,
                        PurchaseItems.transaction_id
                        == InstructorEarnings.transaction_id,
                    )
                    .join(Courses, Courses.id == PurchaseItems.course_id)
                    .join(User, User.id == PurchaseItems.user_id)
                    .join(
                        RefundRequests,
                        RefundRequests.purchase_item_id == PurchaseItems.id,
                        isouter=True,
                    )
                    .where(InstructorEarnings.status.in_(["holding", "freeze"]))
                )
            else:
                query = (
                    select(
                        InstructorEarnings,
                        PurchaseItems,
                        Courses,
                        User,  # student
                        RefundRequests,
                    )
                    .join(
                        PurchaseItems,
                        PurchaseItems.transaction_id
                        == InstructorEarnings.transaction_id,
                    )
                    .join(Courses, Courses.id == PurchaseItems.course_id)
                    .join(User, User.id == PurchaseItems.user_id)
                    .join(
                        RefundRequests,
                        RefundRequests.purchase_item_id == PurchaseItems.id,
                        isouter=True,
                    )
                    .where(InstructorEarnings.instructor_id == instructor_id)
                    .where(InstructorEarnings.status.in_(["holding", "freeze"]))
                )

            # ------------------------------------------------------
            # SEARCH (course.title, student.fullname)
            # ------------------------------------------------------
            if search:
                search_like = f"%{search.lower()}%"
                query = query.where(
                    or_(
                        func.lower(Courses.title).like(search_like),
                        func.lower(User.fullname).like(search_like),
                    )
                )

            # ------------------------------------------------------
            # FILTER
            # ------------------------------------------------------
            if status:
                query = query.where(InstructorEarnings.status == status)

            if course_id:
                query = query.where(Courses.id == course_id)

            if student_id:
                query = query.where(User.id == student_id)

            if date_from and date_to:
                query = query.where(
                    InstructorEarnings.created_at.between(date_from, date_to)
                )

            query = query.order_by(sort_column).offset(offset).limit(limit)

            # ------------------------------------------------------
            # Execute
            # ------------------------------------------------------
            rows = (await self.db.execute(query)).all()

            # ------------------------------------------------------
            # Count total
            # ------------------------------------------------------
            total_query = (
                select(func.count())
                .select_from(InstructorEarnings)
                .join(
                    PurchaseItems,
                    PurchaseItems.transaction_id == InstructorEarnings.transaction_id,
                )
                .join(Courses, Courses.id == PurchaseItems.course_id)
                .join(User, User.id == PurchaseItems.user_id)
                .where(InstructorEarnings.instructor_id == instructor_id)
                .where(InstructorEarnings.status.in_(["holding", "freeze"]))
            )

            if search:
                total_query = total_query.where(
                    or_(
                        func.lower(Courses.title).like(search_like),
                        func.lower(User.fullname).like(search_like),
                    )
                )

            if status:
                total_query = total_query.where(InstructorEarnings.status == status)

            if course_id:
                total_query = total_query.where(Courses.id == course_id)

            if student_id:
                total_query = total_query.where(User.id == student_id)

            if date_from and date_to:
                total_query = total_query.where(
                    InstructorEarnings.created_at.between(date_from, date_to)
                )

            total = (await self.db.scalar(total_query)) or 0

            # ------------------------------------------------------
            # Build Response
            # ------------------------------------------------------
            data = []
            for earnings, item, course, student, refund in rows:
                data.append(
                    {
                        "earnings_id": str(earnings.id),
                        "status": earnings.status,  # holding | freeze
                        "amount_instructor": float(earnings.amount_instructor),
                        "hold_until": earnings.hold_until,
                        "created_at": earnings.created_at,
                        "course": {
                            "course_id": str(course.id),
                            "title": course.title,
                            "thumbnail": course.thumbnail_url,
                        },
                        "student": {
                            "id": str(student.id),
                            "fullname": student.fullname,
                            "avatar": student.avatar,
                        },
                        "purchase_item_id": str(item.id),
                        "refund": {
                            "refund_id": str(refund.id) if refund else None,
                            "status": refund.status if refund else None,
                            "reason": refund.reason if refund else None,
                        },
                    }
                )

            return {
                "page": page,
                "limit": limit,
                "total": total,
                "items": data,
            }

        except Exception as e:
            print("Error get_instructor_pending_earnings:", e)
            raise HTTPException(500, "Lỗi khi lấy danh sách earnings đang giữ.")

    async def get_holding_students_minimal(
        self,
        instructor_id: uuid.UUID | None,
        search: str | None = None,
        limit: int = 10,
        role: str = "LECTURER",
    ):
        try:
            if role == "ADMIN":
                query = (
                    select(User)
                    .join(PurchaseItems, PurchaseItems.user_id == User.id)
                    .join(
                        InstructorEarnings,
                        InstructorEarnings.transaction_id
                        == PurchaseItems.transaction_id,
                    )
                    .where(InstructorEarnings.status == "holding")
                    .order_by(InstructorEarnings.created_at.asc())
                    .limit(limit)
                )
            else:
                query = (
                    select(User)
                    .join(PurchaseItems, PurchaseItems.user_id == User.id)
                    .join(
                        InstructorEarnings,
                        InstructorEarnings.transaction_id
                        == PurchaseItems.transaction_id,
                    )
                    .where(InstructorEarnings.instructor_id == instructor_id)
                    .where(InstructorEarnings.status == "holding")
                    .order_by(InstructorEarnings.created_at.asc())
                    .limit(limit)
                )

            if search:
                s = f"%{search.lower()}%"
                query = query.where(func.lower(User.fullname).like(s))

            rows = (await self.db.execute(query)).scalars().all()

            return [
                {
                    "id": str(u.id),
                    "fullname": u.fullname,
                    "avatar": u.avatar,
                }
                for u in rows
            ]

        except Exception as e:
            print("Error get_holding_students_minimal:", e)
            raise HTTPException(500, "Lỗi khi lấy danh sách học viên.")

    async def get_holding_lecturer_minimal(
        self,
        search: str | None = None,
        limit: int = 10,
    ):
        try:
            # JOIN chính xác:
            # InstructorEarnings.instructor_id → User.id
            query = (
                select(User)
                .join(InstructorEarnings, InstructorEarnings.instructor_id == User.id)
                .where(InstructorEarnings.status == "holding")
                .order_by(InstructorEarnings.created_at.asc())
                .limit(limit)
            )

            if search:
                s = f"%{search.lower()}%"
                query = query.where(func.lower(User.fullname).like(s))

            # tránh bị duplicate nếu 1 GV có nhiều earnings
            rows = (await self.db.execute(query.distinct(User.id))).scalars().all()

            return [
                {
                    "id": str(u.id),
                    "fullname": u.fullname,
                    "avatar": u.avatar,
                }
                for u in rows
            ]

        except Exception as e:
            print("Error get_holding_lecturer_minimal:", e)
            raise HTTPException(500, "Lỗi khi lấy danh sách giảng viên.")

    async def get_holding_courses_minimal(
        self,
        instructor_id: uuid.UUID | None,
        search: str | None = None,
        limit: int = 10,
        role: str = "LECTURER",
    ):
        try:
            if role == "ADMIN":
                query = (
                    select(Courses)
                    .join(PurchaseItems, PurchaseItems.course_id == Courses.id)
                    .join(
                        InstructorEarnings,
                        InstructorEarnings.transaction_id
                        == PurchaseItems.transaction_id,
                    )
                    .where(InstructorEarnings.status == "holding")
                    .order_by(InstructorEarnings.created_at.asc())
                    .limit(limit)
                )
            else:
                query = (
                    select(Courses)
                    .join(PurchaseItems, PurchaseItems.course_id == Courses.id)
                    .join(
                        InstructorEarnings,
                        InstructorEarnings.transaction_id
                        == PurchaseItems.transaction_id,
                    )
                    .where(InstructorEarnings.instructor_id == instructor_id)
                    .where(InstructorEarnings.status == "holding")
                    .order_by(InstructorEarnings.created_at.asc())
                    .limit(limit)
                )

            if search:
                s = f"%{search.lower()}%"
                query = query.where(func.lower(Courses.title).like(s))

            rows = (await self.db.execute(query)).scalars().all()

            return [
                {
                    "id": str(c.id),
                    "title": c.title,
                    "thumbnail": c.thumbnail_url,
                }
                for c in rows
            ]

        except Exception as e:
            print("Error get_holding_courses_minimal:", e)
            raise HTTPException(500, "Lỗi khi lấy danh sách khóa học.")
