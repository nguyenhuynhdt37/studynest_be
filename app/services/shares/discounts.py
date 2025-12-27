import uuid
from typing import List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import (
    Categories,
    Courses,
    DiscountHistory,
    Discounts,
    DiscountTargets,
    PurchaseItems,
    User,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_utc_naive
from app.schemas.shares.discounts import DiscountCreateSchema, DiscountTargetItem


class DiscountService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def create_discount_async(
        self,
        schema: DiscountCreateSchema,
        created_by: uuid.UUID,
        created_role: str,
    ):
        """
        Tạo mã giảm giá:
        - ADMIN: toàn quyền, có thể auto target weak courses hoặc global/category/course
        - LECTURER: chỉ được tạo mã giảm giá theo khóa học thuộc sở hữu
        """

        try:
            # ============================
            # 1) VALIDATE DATE
            # ============================
            if schema.start_at >= schema.end_at:
                raise HTTPException(400, "start_at phải nhỏ hơn end_at")

            # ============================
            # 2) VALIDATE DISCOUNT TYPE
            # ============================
            if schema.discount_type == "percent":
                if not schema.percent_value or not (1 <= schema.percent_value <= 100):
                    raise HTTPException(
                        400, "percent_value phải nằm trong khoảng 1 - 100"
                    )
                schema.fixed_value = None
            elif schema.discount_type == "fixed":
                if not schema.fixed_value or schema.fixed_value <= 0:
                    raise HTTPException(400, "fixed_value không hợp lệ")
                schema.percent_value = None
            else:
                raise HTTPException(400, "discount_type không hợp lệ")

            # ============================
            # 3) CHECK DUPLICATE CODE
            # ============================
            existed = await self.db.scalar(
                select(Discounts.id).where(
                    func.lower(Discounts.discount_code) == schema.discount_code.lower()
                )
            )
            if existed:
                raise HTTPException(
                    400, f"Mã giảm giá '{schema.discount_code}' đã tồn tại."
                )

            is_admin = created_role == "ADMIN"

            # ============================
            # 4) LECTURER RESTRICTIONS
            # ============================
            if created_role == "LECTURER":
                # Giảng viên không được auto-target weak courses
                if schema.auto_targets_weak_courses:
                    raise HTTPException(
                        403, "Giảng viên không được dùng auto_targets_weak_courses."
                    )

                # Giảng viên không được tạo mã theo category/global thật
                if schema.applies_to == "category":
                    raise HTTPException(
                        403, "Giảng viên không được tạo giảm giá theo category."
                    )

                # Nếu giảng viên chọn global → map sang tất cả khóa học của họ
                if schema.applies_to in ["global", "all"]:
                    course_ids = (
                        await self.db.scalars(
                            select(Courses.id).where(
                                Courses.instructor_id == created_by
                            )
                        )
                    ).all()

                    if not course_ids:
                        raise HTTPException(
                            400, "Bạn chưa có khóa học nào để áp dụng mã giảm giá."
                        )

                    schema.applies_to = "course"
                    schema.targets = [
                        DiscountTargetItem(course_id=c_id) for c_id in course_ids
                    ]

                # Tới đây, giảng viên chỉ còn applies_to = "course"
                if schema.applies_to == "course":
                    if not schema.targets or len(schema.targets) == 0:
                        raise HTTPException(400, "Giảng viên phải chỉ định khóa học.")

                    # Check quyền sở hữu từng course
                    for target in schema.targets:
                        if not target.course_id:
                            raise HTTPException(400, "Thiếu course_id trong target.")

                        owned = await self.db.scalar(
                            select(Courses.id).where(
                                Courses.id == target.course_id,
                                Courses.instructor_id == created_by,
                            )
                        )
                        if not owned:
                            raise HTTPException(
                                403,
                                f"Bạn không có quyền tạo giảm giá cho khóa học {target.course_id}",
                            )

            # ============================
            # 5) BUILD TARGET LIST
            # ============================

            final_targets: list[DiscountTargetItem] = []

            # --- CASE A: Admin auto-target weak courses ---
            if is_admin and schema.auto_targets_weak_courses:
                weak_ids = await self.get_all_weak_course_ids_async()
                final_targets = [
                    DiscountTargetItem(course_id=uuid.UUID(str(cid)))
                    for cid in weak_ids
                ]

            # --- CASE B: Admin/lecturer dùng target thủ công ---
            elif schema.targets:
                final_targets = schema.targets

            # --- CASE C: applies_to global/all → không cần targets ---
            elif schema.applies_to in ["global", "all"]:
                final_targets = []

            # --- CASE D: applies_to course/category mà không có targets ---
            elif schema.applies_to in ["course", "category"]:
                raise HTTPException(
                    400,
                    f"Mã giảm giá '{schema.applies_to}' yêu cầu targets.",
                )

            # ============================
            # 6) INSERT DISCOUNT
            # ============================
            discount = Discounts(
                id=uuid.uuid4(),
                name=schema.name,
                description=schema.description,
                discount_code=schema.discount_code,
                is_hidden=schema.is_hidden or False,
                created_by=created_by,
                created_role=created_role,
                applies_to=schema.applies_to,
                discount_type=schema.discount_type,
                percent_value=schema.percent_value,
                fixed_value=schema.fixed_value,
                usage_limit=schema.usage_limit,
                per_user_limit=schema.per_user_limit,
                start_at=await to_utc_naive(schema.start_at),
                end_at=await to_utc_naive(schema.end_at),
                is_active=True,
            )

            self.db.add(discount)
            await self.db.flush()

            # ============================
            # 7) INSERT TARGET RECORDS
            # ============================
            if discount.applies_to in ["course", "category"] and final_targets:
                for t in final_targets:
                    self.db.add(
                        DiscountTargets(
                            discount_id=discount.id,
                            course_id=t.course_id,
                            category_id=t.category_id,
                        )
                    )

            await self.db.commit()
            await self.db.refresh(discount)

            # ============================
            # 8) RETURN
            # ============================
            return {
                "id": str(discount.id),
                "discount_code": discount.discount_code,
                "applies_to": discount.applies_to,
                "targets_count": len(final_targets),
                "auto_generated_from_weak_courses": schema.auto_targets_weak_courses,
            }

        except HTTPException:
            # giữ nguyên lỗi nghiệp vụ
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Tạo mã giảm giá thất bại: {e}")

    # ============================================================
    # 1. LIST DISCOUNTS (FILTER + SORT)
    # ============================================================
    async def get_discounts_async(
        self,
        user: User,
        role: str,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        applies_to: Optional[str] = None,
        discount_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        validity: Optional[str] = None,
        sort_by: str = "created_at",
        order_dir: str = "desc",
    ):
        now = get_now()

        valid_sort = {
            "name": Discounts.name,
            "discount_code": Discounts.discount_code,
            "applies_to": Discounts.applies_to,
            "discount_type": Discounts.discount_type,
            "usage_count": Discounts.usage_count,
            "start_at": Discounts.start_at,
            "end_at": Discounts.end_at,
            "created_at": Discounts.created_at,
        }

        sort_field = valid_sort.get(sort_by, Discounts.created_at)
        sort_order = (
            sort_field.desc() if order_dir.lower() == "desc" else sort_field.asc()
        )

        # ====================================
        # 🎯 ROLE FILTER
        # ====================================
        if role == "LECTURER":
            # Lecturer chỉ xem discount họ tạo + chỉ allowed course
            stmt = select(Discounts).where(
                Discounts.created_role == "LECTURER",
                Discounts.created_by == user.id,
                Discounts.applies_to == "course",  # CHỈ COURSE
            )

        elif role == "ADMIN":
            # Admin xem toàn bộ discount do Admin tạo (course+category+global)
            stmt = select(Discounts).where(Discounts.created_role == "ADMIN")

        else:
            raise HTTPException(403, "Role không hợp lệ.")

        # ============================
        # SEARCH
        # ============================
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Discounts.name).like(like),
                    func.lower(Discounts.discount_code).like(like),
                )
            )

        # ============================
        # FILTER applies_to (nếu ADMIN muốn lọc select)
        # ============================
        if applies_to:
            stmt = stmt.where(Discounts.applies_to == applies_to)

        # ============================
        # discount_type
        # ============================
        if discount_type:
            stmt = stmt.where(Discounts.discount_type == discount_type)

        # ============================
        # is_active
        # ============================
        if is_active is not None:
            stmt = stmt.where(Discounts.is_active.is_(is_active))

        # ============================
        # VALIDITY
        # ============================
        if validity:
            if validity == "expired":
                stmt = stmt.where(Discounts.end_at < now)
            elif validity == "running":
                stmt = stmt.where(
                    Discounts.start_at <= now,
                    Discounts.end_at >= now,
                    Discounts.is_active.is_(True),
                )
            elif validity == "upcoming":
                stmt = stmt.where(Discounts.start_at > now)

        # ============================
        # COUNT
        # ============================
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))

        # ============================
        # PAGINATION
        # ============================
        offset = (page - 1) * limit
        stmt = stmt.order_by(sort_order).limit(limit).offset(offset)

        items = (await self.db.execute(stmt)).scalars().all()

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "items": items,
        }

    # ============================================================
    # 2. DISCOUNT DETAIL
    # ============================================================

    async def get_discount_detail_async(
        self,
        discount_id: uuid.UUID,
        user: User,
        role: str,
    ):
        """
        Lấy chi tiết mã giảm giá:
        - Thông tin discount
        - Target (course/category)
        - Lịch sử sử dụng
        - Hạn chế quyền cho giảng viên
        """

        # ============================
        # 1) LẤY DISCOUNT
        # ============================
        discount: Discounts | None = await self.db.scalar(
            select(Discounts).where(Discounts.id == discount_id)
        )

        if not discount:
            raise HTTPException(404, "Không tìm thấy mã giảm giá.")

        # ============================
        # 2) KIỂM TRA QUYỀN
        # ============================
        if role == "LECTURER" and discount.created_by != user.id:
            raise HTTPException(403, "Bạn không có quyền xem mã giảm giá này.")

        # ============================
        # 3) LẤY TARGET (COURSE / CATEGORY)
        # ============================
        target_rows = (
            await self.db.execute(
                select(
                    DiscountTargets,
                    Courses.title.label("course_title"),
                    Categories.name.label("category_name"),
                )
                .outerjoin(Courses, Courses.id == DiscountTargets.course_id)
                .outerjoin(Categories, Categories.id == DiscountTargets.category_id)
                .where(DiscountTargets.discount_id == discount_id)
            )
        ).all()

        targets = []
        for tgt, course_title, category_name in target_rows:
            targets.append(
                {
                    "course_id": tgt.course_id,
                    "course_title": course_title,
                    "category_id": tgt.category_id,
                    "category_name": category_name,
                }
            )

        # ============================
        # 4) LỊCH SỬ SỬ DỤNG
        # ============================
        history_rows = (
            await self.db.execute(
                select(
                    DiscountHistory,
                    PurchaseItems,
                    User.fullname.label("user_name"),
                    User.avatar.label("avatar"),
                    Courses.title.label("course_title"),
                )
                .join(
                    PurchaseItems, PurchaseItems.id == DiscountHistory.purchase_item_id
                )
                .join(User, User.id == PurchaseItems.user_id)
                .join(Courses, Courses.id == PurchaseItems.course_id)
                .where(DiscountHistory.discount_id == discount_id)
                .order_by(DiscountHistory.created_at.desc())
            )
        ).all()

        usage_history = []
        for dh, pi, user_name, avatar, course_title in history_rows:
            usage_history.append(
                {
                    "user_id": pi.user_id,
                    "user_name": user_name,
                    "avatar": avatar,
                    "course_id": pi.course_id,
                    "course_title": course_title,
                    "discounted_amount": float(dh.discounted_amount or 0),
                    "used_at": dh.created_at,
                }
            )

        # ============================
        # 5) FORMAT DISCOUNT TRẢ VỀ
        # ============================
        discount_data = {
            "id": str(discount.id),
            "code": discount.discount_code,
            "name": discount.name,
            "description": discount.description,
            "applies_to": discount.applies_to,
            "discount_type": discount.discount_type,
            "percent_value": discount.percent_value,
            "fixed_value": discount.fixed_value,
            "usage_limit": discount.usage_limit,
            "usage_count": discount.usage_count,
            "per_user_limit": discount.per_user_limit,
            "start_at": discount.start_at,
            "end_at": discount.end_at,
            "is_active": discount.is_active,
            "is_hidden": discount.is_hidden,
        }

        return {
            "discount": discount_data,
            "targets": targets,
            "usage_history": usage_history,
        }

    # ============================================================
    # 3. GET AVAILABLE DISCOUNTS
    # ============================================================
    async def get_available_discounts(
        self, user_id: uuid.UUID, course_ids: List[uuid.UUID]
    ):
        now = get_now()

        courses = (
            (await self.db.execute(select(Courses).where(Courses.id.in_(course_ids))))
            .scalars()
            .all()
        )
        if not courses:
            return []

        course_categories = {c.id: c.category_id for c in courses}

        discounts = (
            (
                await self.db.execute(
                    select(Discounts).where(Discounts.is_active, ~Discounts.is_hidden)
                )
            )
            .scalars()
            .all()
        )

        all_targets = (
            (
                await self.db.execute(
                    select(DiscountTargets).where(
                        DiscountTargets.discount_id.in_([d.id for d in discounts])
                    )
                )
            )
            .scalars()
            .all()
        )

        target_map = {}
        for t in all_targets:
            target_map.setdefault(
                t.discount_id, {"course_ids": set(), "category_ids": set()}
            )
            if t.course_id:
                target_map[t.discount_id]["course_ids"].add(t.course_id)
            if t.category_id:
                target_map[t.discount_id]["category_ids"].add(t.category_id)

        available = []

        for d in discounts:
            if d.start_at and d.start_at > now:
                continue
            if d.end_at and d.end_at < now:
                continue
            if d.usage_limit and d.usage_count >= d.usage_limit:
                continue

            # per-user-limit theo giao dịch
            used_transactions = (
                await self.db.execute(
                    select(
                        func.count(func.distinct(PurchaseItems.transaction_id))
                    ).where(
                        PurchaseItems.user_id == user_id,
                        PurchaseItems.discount_id == d.id,
                    )
                )
            ).scalar_one()

            if d.per_user_limit and used_transactions >= d.per_user_limit:
                continue

            targets = target_map.get(d.id, {"course_ids": set(), "category_ids": set()})

            # ✅ Mã global/all áp dụng cho tất cả khóa học
            if d.applies_to in ["global", "all"]:
                can_apply = True
            else:
                # Mã course/category cần check targets
                can_apply = False
                for c in courses:
                    if (
                        c.id in targets["course_ids"]
                        or course_categories[c.id] in targets["category_ids"]
                    ):
                        can_apply = True
                        break

            if not can_apply:
                continue

            available.append(d)

        def discount_strength(discount: Discounts):
            targets = target_map.get(
                discount.id, {"course_ids": set(), "category_ids": set()}
            )
            max_reduce = 0

            for c in courses:
                # ✅ Mã global/all áp dụng cho tất cả courses
                applies_to_course = (
                    discount.applies_to in ["global", "all"]
                    or c.id in targets["course_ids"]
                    or course_categories[c.id] in targets["category_ids"]
                )
                
                if applies_to_course:
                    if discount.discount_type == "percent":
                        reduced = float(c.base_price or 0) * (
                            float(discount.percent_value or 0) / 100
                        )
                    else:
                        reduced = float(discount.fixed_value or 0)

                    max_reduce = max(max_reduce, reduced)

            return max_reduce

        available.sort(key=discount_strength, reverse=True)

        return {"count": len(available), "items": available}

    async def calculate_discount_apply(
        self,
        user_id: uuid.UUID,
        course_ids: List[uuid.UUID],
        discount_input: str,
    ):
        # 0. Lấy danh sách khóa học trước (dù mã có hợp lệ hay không)
        courses = (
            (await self.db.execute(select(Courses).where(Courses.id.in_(course_ids))))
            .scalars()
            .all()
        )

        # Không có khóa nào → trả về rỗng luôn
        if not courses:
            return {
                "discount_id": None,
                "discount_code": discount_input,
                "discount_name": None,
                "discount_description": None,
                "discount_applies_to": None,
                "discount_type": None,
                "discount_percent_value": None,
                "discount_fixed_value": None,
                "discount_usage_limit": None,
                "discount_usage_count": None,
                "discount_per_user_limit": None,
                "discount_is_active": None,
                "discount_is_hidden": None,
                "discount_start_at": None,
                "discount_end_at": None,
                "user_used_transactions": 0,
                "user_remaining_uses": None,
                "items": [],
                "total_discount": 0.0,
                "total_price_after": 0.0,
            }

        def build_no_discount_response(
            reason: str, discount_obj=None, used_transactions: int = 0
        ):
            items = []
            total_price_after = 0.0

            for c in courses:
                price = float(c.base_price or 0)
                total_price_after += price
                items.append(
                    {
                        "course_id": c.id,
                        "course_title": c.title,
                        "base_price": price,
                        "discounted_amount": 0.0,
                        "final_price": price,
                        "applied": False,
                        "reason": reason,
                    }
                )

            # nếu không có discount_obj thì tất cả discount_* = None
            per_user_limit = getattr(discount_obj, "per_user_limit", None)
            remaining_uses = (
                max(0, per_user_limit - used_transactions)
                if per_user_limit is not None
                else None
            )

            return {
                "discount_id": getattr(discount_obj, "id", None),
                "discount_code": getattr(discount_obj, "discount_code", discount_input),
                "discount_name": getattr(discount_obj, "name", None),
                "discount_description": getattr(discount_obj, "description", None),
                "discount_applies_to": getattr(discount_obj, "applies_to", None),
                "discount_type": getattr(discount_obj, "discount_type", None),
                "discount_percent_value": getattr(discount_obj, "percent_value", None),
                "discount_fixed_value": getattr(discount_obj, "fixed_value", None),
                "discount_usage_limit": getattr(discount_obj, "usage_limit", None),
                "discount_usage_count": getattr(discount_obj, "usage_count", None),
                "discount_per_user_limit": per_user_limit,
                "discount_is_active": getattr(discount_obj, "is_active", None),
                "discount_is_hidden": getattr(discount_obj, "is_hidden", None),
                "discount_start_at": getattr(discount_obj, "start_at", None),
                "discount_end_at": getattr(discount_obj, "end_at", None),
                "user_used_transactions": used_transactions,
                "user_remaining_uses": remaining_uses,
                "items": items,
                "total_discount": 0.0,
                "total_price_after": total_price_after,
            }

        # 1. Tìm discount theo id hoặc theo code
        discount_obj = None

        # detect UUID
        try:
            parsed = uuid.UUID(discount_input)
            discount_obj = await self.db.scalar(
                select(Discounts).where(Discounts.id == parsed)
            )
        except Exception:
            pass

        # detect code
        if not discount_obj:
            discount_obj = await self.db.scalar(
                select(Discounts).where(
                    func.lower(Discounts.discount_code) == discount_input.lower()
                )
            )

        # Không tìm thấy mã → trả nhưng vẫn đúng format
        if not discount_obj:
            return build_no_discount_response("Mã giảm giá không tồn tại")

        discount = discount_obj
        discount_id = discount.id
        now = get_now()

        # 2. Validate thời gian, trạng thái, lượt dùng… → nếu fail thì cũng trả format thống nhất

        if discount.start_at and discount.start_at > now:
            return build_no_discount_response(
                "Mã giảm giá chưa đến thời gian sử dụng", discount
            )

        if discount.end_at and discount.end_at < now:
            return build_no_discount_response("Mã giảm giá đã hết hạn", discount)

        if not discount.is_active:
            return build_no_discount_response("Mã giảm giá không hợp lệ", discount)

        if discount.usage_limit and discount.usage_count >= discount.usage_limit:
            return build_no_discount_response("Mã giảm giá đã hết lượt dùng", discount)

        # per-user-limit theo GIAO DỊCH, không theo số khóa
        used_transactions = (
            await self.db.execute(
                select(func.count(func.distinct(PurchaseItems.transaction_id))).where(
                    PurchaseItems.user_id == user_id,
                    PurchaseItems.discount_id == discount_id,
                )
            )
        ).scalar_one()

        if discount.per_user_limit and used_transactions >= discount.per_user_limit:
            return build_no_discount_response(
                "Bạn đã sử dụng hết lượt dùng mã này", discount, used_transactions
            )

        # 3. Lấy target (course / category) của mã
        target_rows = (
            (
                await self.db.execute(
                    select(DiscountTargets).where(
                        DiscountTargets.discount_id == discount_id
                    )
                )
            )
            .scalars()
            .all()
        )

        target_course_ids = {t.course_id for t in target_rows if t.course_id}
        target_category_ids = {t.category_id for t in target_rows if t.category_id}

        results = []
        total_discount = 0.0
        total_price_after = 0.0

        for c in courses:
            price = float(c.base_price or 0)

            can_apply = (
                (not target_course_ids and not target_category_ids)
                # nếu không có target cụ thể → hiểu là áp cho tất cả (tuỳ rule business)
                or c.id in target_course_ids
                or c.category_id in target_category_ids
            )

            # Không áp dụng cho khóa này
            if not can_apply:
                results.append(
                    {
                        "course_id": c.id,
                        "course_title": c.title,
                        "base_price": price,
                        "discounted_amount": 0.0,
                        "final_price": price,
                        "applied": False,
                        "reason": "Mã không áp dụng cho khóa học này",
                    }
                )
                total_price_after += price
                continue

            # 4. Tính giảm
            if discount.discount_type == "percent":
                percent_value = float(discount.percent_value or 0)
                discount_amount = price * (percent_value / 100.0)
            else:
                discount_amount = float(discount.fixed_value or 0)

            discount_amount = min(discount_amount, price)
            final_price = price - discount_amount

            results.append(
                {
                    "course_id": c.id,
                    "course_title": c.title,
                    "base_price": price,
                    "discounted_amount": discount_amount,
                    "final_price": final_price,
                    "applied": True,
                }
            )

            total_discount += discount_amount
            total_price_after += final_price

        # thông tin per-user
        per_user_limit = discount.per_user_limit
        remaining_uses = (
            max(0, per_user_limit - used_transactions)
            if per_user_limit is not None
            else None
        )

        return {
            "discount_id": discount_id,
            "discount_code": discount.discount_code,
            "discount_name": discount.name,
            "discount_description": discount.description,
            "discount_applies_to": discount.applies_to,
            "discount_type": discount.discount_type,
            "discount_percent_value": discount.percent_value,
            "discount_fixed_value": discount.fixed_value,
            "discount_usage_limit": discount.usage_limit,
            "discount_usage_count": discount.usage_count,
            "discount_per_user_limit": per_user_limit,
            "discount_is_active": discount.is_active,
            "discount_is_hidden": discount.is_hidden,
            "discount_start_at": discount.start_at,
            "discount_end_at": discount.end_at,
            "user_used_transactions": used_transactions,
            "user_remaining_uses": remaining_uses,
            "items": results,
            "total_discount": total_discount,
            "total_price_after": total_price_after,
        }

    async def toggle_discount_active_async(
        self,
        discount_id: uuid.UUID,
        user: User,
        role: str,
        is_active: bool | None = None,
    ):
        """
        Bật / tắt trạng thái mã giảm giá.
        - ADMIN: full quyền.
        - LECTURER: chỉ bật/tắt được mã mình tạo.
        """

        discount = await self.db.scalar(
            select(Discounts).where(Discounts.id == discount_id)
        )
        if not discount:
            raise HTTPException(404, "Không tìm thấy mã giảm giá.")

        # Quyền
        if role == "LECTURER" and discount.created_by != user.id:
            raise HTTPException(403, "Bạn không có quyền chỉnh sửa mã giảm giá này.")

        # ADMIN: bỏ qua check luôn (full quyền)

        # Toggle hoặc set cứng
        if is_active is None:
            discount.is_active = not bool(discount.is_active)
        else:
            discount.is_active = bool(is_active)

        await self.db.commit()
        await self.db.refresh(discount)

        return {
            "id": str(discount.id),
            "discount_code": discount.discount_code,
            "is_active": discount.is_active,
            "is_hidden": discount.is_hidden,
        }

    async def delete_discount_async(
        self,
        discount_id: uuid.UUID,
        user: User,
        role: str,
    ):
        """
        Xóa mã giảm giá:
        - Chỉ xóa nếu mã chưa từng được sử dụng:
            + Không có DiscountHistory
            + Không có PurchaseItems.discount_id
        - ADMIN: xóa mọi mã.
        - LECTURER: chỉ xóa mã do mình tạo.
        """

        discount = await self.db.scalar(
            select(Discounts).where(Discounts.id == discount_id)
        )
        if not discount:
            raise HTTPException(404, "Không tìm thấy mã giảm giá.")

        # Quyền
        if role == "LECTURER" and discount.created_by != user.id:
            raise HTTPException(403, "Bạn không có quyền xóa mã giảm giá này.")

        # ADMIN: vượt qua luôn

        # 1) Check lịch sử dùng
        used_hist = await self.db.scalar(
            select(func.count(DiscountHistory.id)).where(
                DiscountHistory.discount_id == discount_id
            )
        )

        used_items = await self.db.scalar(
            select(func.count(PurchaseItems.id)).where(
                PurchaseItems.discount_id == discount_id
            )
        )

        if (used_hist or 0) > 0 or (used_items or 0) > 0:
            raise HTTPException(
                400,
                "Mã giảm giá đã từng được sử dụng — không thể xóa. Hãy tắt (inactive) thay vì xóa.",
            )

        # 2) Xóa target trước
        await self.db.execute(
            delete(DiscountTargets).where(DiscountTargets.discount_id == discount_id)
        )

        # 3) Xóa discount
        await self.db.delete(discount)
        await self.db.commit()

        return {
            "deleted": True,
            "discount_id": str(discount_id),
            "message": "Đã xóa mã giảm giá (chưa từng được dùng).",
        }

    async def edit_discount_async(
        self,
        discount_id: uuid.UUID,
        schema,
        user: User,
        role: str,
    ):
        try:
            # ============================
            # 1) LẤY MÃ GIẢM GIÁ
            # ============================
            discount = await self.db.scalar(
                select(Discounts).where(Discounts.id == discount_id)
            )
            if not discount:
                raise HTTPException(404, "Không tìm thấy mã giảm giá.")

            is_admin = role == "ADMIN"
            is_lecturer = role == "LECTURER"

            # ============================
            # 2) CHECK QUYỀN
            # ============================
            if is_lecturer and discount.created_by != user.id:
                raise HTTPException(403, "Bạn không có quyền sửa mã này.")

            # ============================
            # 3) CHECK USED COUNT
            # ============================
            used_count = await self.db.scalar(
                select(func.count(DiscountHistory.id)).where(
                    DiscountHistory.discount_id == discount_id
                )
            )

            if used_count > 0:
                # Không được đổi code/type
                if schema.discount_code != discount.discount_code:
                    raise HTTPException(
                        400, "Mã đã được sử dụng — không thể đổi discount_code."
                    )
                if schema.discount_type != discount.discount_type:
                    raise HTTPException(
                        400, "Mã đã được sử dụng — không thể đổi discount_type."
                    )

            # ============================
            # 4) VALIDATE DISCOUNT TYPE
            # ============================
            if schema.discount_type == "percent":
                if not schema.percent_value or not (1 <= schema.percent_value <= 100):
                    raise HTTPException(
                        400, "percent_value phải nằm trong khoảng 1 - 100"
                    )
                schema.fixed_value = None

            elif schema.discount_type == "fixed":
                if not schema.fixed_value or schema.fixed_value <= 0:
                    raise HTTPException(400, "fixed_value không hợp lệ")
                schema.percent_value = None

            else:
                raise HTTPException(400, "discount_type không hợp lệ")

            # ============================
            # 5) VALIDATE DATE
            # ============================
            if schema.start_at >= schema.end_at:
                raise HTTPException(400, "start_at phải nhỏ hơn end_at")

            # ============================
            # 6) LECTURER RESTRICTIONS
            # ============================
            if is_lecturer:
                # Giảng viên không được sửa category/global thật
                if schema.applies_to == "category":
                    raise HTTPException(
                        403, "Giảng viên không được sửa giảm giá theo category."
                    )

                # Nếu chọn global → map sang toàn bộ khóa học của họ
                if schema.applies_to in ["global", "all"]:
                    owned_courses = (
                        await self.db.scalars(
                            select(Courses.id).where(Courses.instructor_id == user.id)
                        )
                    ).all()

                    if not owned_courses:
                        raise HTTPException(400, "Bạn không có khóa học nào.")

                    schema.applies_to = "course"
                    schema.targets = [
                        DiscountTargetItem(course_id=c_id) for c_id in owned_courses
                    ]

                # Lúc này chỉ còn applies_to = "course"
                for t in schema.targets or []:
                    if t.course_id:
                        owned = await self.db.scalar(
                            select(Courses.id).where(
                                Courses.id == t.course_id,
                                Courses.instructor_id == user.id,
                            )
                        )
                        if not owned:
                            raise HTTPException(
                                403,
                                f"Bạn không có quyền áp mã vào khóa {t.course_id}",
                            )

            # ============================
            # 7) UPDATE DISCOUNT FIELDS
            # ============================
            discount.name = schema.name
            discount.description = schema.description
            discount.is_hidden = schema.is_hidden
            discount.applies_to = schema.applies_to

            if used_count == 0:
                discount.discount_code = schema.discount_code
                discount.discount_type = schema.discount_type

            discount.percent_value = schema.percent_value
            discount.fixed_value = schema.fixed_value
            discount.usage_limit = schema.usage_limit
            discount.per_user_limit = schema.per_user_limit
            discount.start_at = schema.start_at.replace(tzinfo=None)
            discount.end_at = schema.end_at.replace(tzinfo=None)

            # ============================
            # 8) BUILD TARGET LIST CHUẨN
            # ============================
            final_targets = []

            # ---- A: GLOBAL / ALL → không target ----
            if schema.applies_to in ["global", "all"]:
                final_targets = []

            # ---- B: ADMIN auto weak courses ----
            elif is_admin and getattr(schema, "auto_targets_weak_courses", False):
                weak_ids = await self.get_all_weak_course_ids_async()
                final_targets = [
                    DiscountTargetItem(course_id=uuid.UUID(str(cid)))
                    for cid in weak_ids
                ]

            # ---- C: targets thủ công ----
            elif schema.targets:
                final_targets = schema.targets

            # ---- D: Lecturer phải có targets ----
            elif is_lecturer:
                raise HTTPException(400, "Giảng viên phải chỉ định khóa học.")

            # ---- E: Admin thiếu target và không phải global ----
            else:
                raise HTTPException(
                    400,
                    "Admin cần cấu hình target hoặc chọn áp dụng toàn sàn (global/all).",
                )

            # ============================
            # 9) UPDATE TARGET RECORDS
            # ============================
            await self.db.execute(
                delete(DiscountTargets).where(
                    DiscountTargets.discount_id == discount_id
                )
            )

            if schema.applies_to in ["course", "category"]:
                for t in final_targets:
                    self.db.add(
                        DiscountTargets(
                            discount_id=discount.id,
                            course_id=t.course_id,
                            category_id=t.category_id,
                        )
                    )

            await self.db.commit()
            await self.db.refresh(discount)

            return {
                "message": "Cập nhật mã giảm giá thành công.",
                "discount_id": str(discount.id),
                "targets_count": len(final_targets),
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Không thể sửa mã giảm giá: {e}")

    async def get_discount_edit_data_async(
        self,
        discount_id: uuid.UUID,
        user: User,
        role: str,
    ):
        """
        Lấy dữ liệu chi tiết để hiển thị form edit discount:
        - ADMIN xem tất cả
        - LECTURER chỉ xem mã của chính họ
        - Trả về thông tin discount + targets + usage_count
        """

        # ------------------------------
        # 1) LẤY MÃ GIẢM GIÁ
        # ------------------------------
        discount = await self.db.scalar(
            select(Discounts).where(Discounts.id == discount_id)
        )

        if not discount:
            raise HTTPException(404, "Không tìm thấy mã giảm giá.")

        # ------------------------------
        # 2) CHECK QUYỀN
        # ------------------------------
        if role == "LECTURER" and discount.created_by != user.id:
            raise HTTPException(403, "Bạn không có quyền xem mã giảm giá này.")

        # ------------------------------
        # 3) LẤY TARGETS
        # ------------------------------
        target_rows = (
            (
                await self.db.execute(
                    select(DiscountTargets)
                    .where(DiscountTargets.discount_id == discount_id)
                    .order_by(DiscountTargets.course_id, DiscountTargets.category_id)
                )
            )
            .scalars()
            .all()
        )

        targets = [
            {
                "course_id": t.course_id,
                "category_id": t.category_id,
            }
            for t in target_rows
        ]

        # ------------------------------
        # 4) ĐẾM LỊCH SỬ SỬ DỤNG
        # ------------------------------
        usage_count = await self.db.scalar(
            select(func.count(DiscountHistory.id)).where(
                DiscountHistory.discount_id == discount_id
            )
        )

        # ------------------------------
        # 5) TRẢ VỀ DỮ LIỆU CHO FORM EDIT
        # ------------------------------
        return {
            "discount_id": str(discount.id),
            "name": discount.name,
            "description": discount.description,
            "discount_code": discount.discount_code,
            "is_hidden": discount.is_hidden,
            "applies_to": discount.applies_to,
            "discount_type": discount.discount_type,
            "percent_value": discount.percent_value,
            "fixed_value": discount.fixed_value,
            "usage_limit": discount.usage_limit,
            "per_user_limit": discount.per_user_limit,
            "start_at": discount.start_at,
            "end_at": discount.end_at,
            "is_active": discount.is_active,
            "targets": targets,
            "usage_count": usage_count,
            "created_by": str(discount.created_by),
            "created_role": discount.created_role,
        }

    async def get_weak_courses_async(self):
        """
        Lấy TOP 100 khóa học yếu nhất để Admin ưu tiên giảm giá.
        Không phân trang. Trả về danh sách đầy đủ.
        """

        # Revenue subquery
        revenue_sub = (
            select(
                PurchaseItems.course_id,
                func.coalesce(func.sum(PurchaseItems.discounted_price), 0).label(
                    "revenue"
                ),
            )
            .group_by(PurchaseItems.course_id)
            .subquery()
        )

        # Weak score expression
        weak_score_expr = func.coalesce(
            (
                (5 - func.coalesce(Courses.rating_avg, 0)) * 0.4
                + (1 / func.nullif(Courses.total_enrolls, 0)) * 0.3
                + (1 / func.nullif(Courses.views, 0)) * 0.2
                + (1 / func.nullif(revenue_sub.c.revenue, 0)) * 0.1
            ),
            0,
        ).label("weak_score")

        # Lấy TOP 100 khóa yếu nhất
        query = (
            select(
                Courses.id,
                Courses.title,
                Courses.rating_avg,
                Courses.views,
                Courses.total_enrolls,
                func.coalesce(revenue_sub.c.revenue, 0).label("revenue"),
                weak_score_expr,
            )
            .outerjoin(revenue_sub, revenue_sub.c.course_id == Courses.id)
            .order_by(desc(weak_score_expr))
            .limit(100)
        )

        rows = (await self.db.execute(query)).all()

        # Format output
        data = []
        for (
            course_id,
            title,
            rating_avg,
            views,
            total_enrolls,
            revenue,
            weak_score,
        ) in rows:
            data.append(
                {
                    "course_id": str(course_id),
                    "title": title,
                    "rating_avg": float(rating_avg or 0),
                    "views": int(views or 0),
                    "total_enrolls": int(total_enrolls or 0),
                    "revenue": float(revenue or 0),
                    "weak_score": float(weak_score or 0),
                }
            )

        return data

    async def get_all_weak_course_ids_async(
        self,
        max_count: int = 100,
    ):
        """
        Lấy danh sách course_id của các khóa học yếu nhất (TOP max_count).
        Dùng cho admin khi tạo mã giảm giá auto cho weak courses.
        """

        # Revenue subquery
        revenue_sub = (
            select(
                PurchaseItems.course_id,
                func.coalesce(func.sum(PurchaseItems.discounted_price), 0).label(
                    "revenue"
                ),
            )
            .group_by(PurchaseItems.course_id)
            .subquery()
        )

        weak_score_expr = func.coalesce(
            (
                (5 - func.coalesce(Courses.rating_avg, 0)) * 0.4
                + (1 / func.nullif(Courses.total_enrolls, 0)) * 0.3
                + (1 / func.nullif(Courses.views, 0)) * 0.2
                + (1 / func.nullif(revenue_sub.c.revenue, 0)) * 0.1
            ),
            0,
        ).label("weak_score")

        query = (
            select(Courses.id, weak_score_expr)
            .outerjoin(revenue_sub, revenue_sub.c.course_id == Courses.id)
            .order_by(desc(weak_score_expr))
            .limit(max_count)  # 🔥 chỉ lấy TOP N
        )

        rows = (await self.db.execute(query)).all()

        return [str(course_id) for course_id, _ in rows]

    async def get_discount_course_list_async(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        instructor_id: uuid.UUID | None = None,
    ):
        """
        Lấy danh sách khóa học nhẹ để dùng trong UI tạo mã giảm giá.
        Cho phép tìm kiếm + phân trang.
        """
        offset = (page - 1) * limit

        query = select(Courses)

        # --- search theo title ---
        if search:
            like_str = f"%{search.lower()}%"
            query = query.where(func.lower(Courses.title).like(like_str))

        # --- nếu lecturer đang tạo mã giảm → chỉ lấy khóa học của họ ---
        if instructor_id:
            query = query.where(Courses.instructor_id == instructor_id)

        # --- ORDER mặc định: khóa học mới nhất ---
        query = query.order_by(desc(Courses.created_at))

        # --- pagination ---
        result: List[Courses | None] = (
            (await self.db.execute(query.offset(offset).limit(limit))).scalars().all()
        )

        # --- total ---
        count_query = select(func.count(Courses.id))
        if search:
            like_str = f"%{search.lower()}%"
            count_query = count_query.where(func.lower(Courses.title).like(like_str))
        if instructor_id:
            count_query = count_query.where(Courses.instructor_id == instructor_id)

        total = await self.db.scalar(count_query)

        # --- định dạng trả về ---
        items = []
        for c in result:
            items.append(
                {
                    "id": str(c.id) if c else None,
                    "title": c.title if c else None,
                    "base_price": float(c.base_price or 0) if c else 0,
                    "thumbnail": c.thumbnail_url if c else None,
                    "rating_avg": float(c.rating_avg or 0) if c else 0,
                    "total_enrolls": c.total_enrolls or 0 if c else 0,
                }
            )

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "items": items,
        }
