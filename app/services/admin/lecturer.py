import uuid
from io import BytesIO

import pandas as pd
from fastapi import Depends, HTTPException, Response
from sqlalchemy import asc, delete, desc, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.database import (
    Courses,
    CourseSections,
    LecturerUpgradePayments,
    Role,
    Transactions,
    User,
    UserRoles,
    Wallets,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_utc_naive


class LecturerService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_lecturers_async(
        self,
        is_verified_email: bool | None,
        is_banned: bool | None,
        search: str | None,
        sort_by: str,
        order: str,
        page: int,
        size: int,
    ):
        # 🔹 Base query: lấy user có role 'LECTURER'
        stmt = (
            select(
                User,
                Wallets.balance.label("wallet_balance"),
                LecturerUpgradePayments.paid_time.label("upgrade_date"),
            )
            .join(UserRoles, UserRoles.user_id == User.id)
            .join(Role, Role.id == UserRoles.role_id)
            .join(Wallets, Wallets.user_id == User.id, isouter=True)
            .join(
                LecturerUpgradePayments,
                LecturerUpgradePayments.user_id == User.id,
                isouter=True,
            )
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(
                Role.role_name == "LECTURER",
                Role.role_name != "ADMIN",
                User.deleted_at.is_(None),
            )
            .group_by(User.id, Wallets.balance, LecturerUpgradePayments.paid_time)
        )

        # 🔹 Bộ lọc nâng cao
        if is_verified_email is not None:
            stmt = stmt.where(User.is_verified_email.is_(is_verified_email))
        if is_banned is not None:
            stmt = stmt.where(User.is_banned.is_(is_banned))
        if search:
            stmt = stmt.where(
                or_(
                    User.fullname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.citizenship_identity.ilike(f"%{search}%"),
                )
            )

        # 🔹 Đếm tổng số giảng viên
        subquery = stmt.subquery()
        total_items = (
            await self.db.scalar(select(func.count()).select_from(subquery)) or 0
        )

        sort_fields = {
            "course_count": User.course_count,
            "rating_avg": User.rating_avg,
            "evaluated_count": User.evaluated_count,
            "student_count": User.student_count,
            "wallet_balance": Wallets.balance,
            "upgrade_date": LecturerUpgradePayments.paid_time,
        }

        sort_column = sort_fields.get(sort_by, getattr(User, sort_by, User.create_at))
        sort_expr = sort_column.asc() if order.lower() == "asc" else sort_column.desc()

        stmt = stmt.order_by(sort_expr).offset((page - 1) * size).limit(size)

        # 🔹 Thực thi truy vấn
        result = await self.db.execute(stmt)
        records = result.all()

        # 🔹 Map dữ liệu trả về
        lecturers = []
        for user, wallet_balance, upgrade_date in records:
            lecturers.append(
                {
                    "id": user.id,
                    "fullname": user.fullname,
                    "email": user.email,
                    "avatar": user.avatar,
                    "bio": user.bio,
                    "citizenship_identity": user.citizenship_identity,
                    "birthday": user.birthday,
                    "conscious": user.conscious,
                    "district": user.district,
                    "course_count": user.course_count or 0,
                    "student_count": user.student_count or 0,
                    "evaluated_count": user.evaluated_count or 0,
                    "rating_avg": float(user.rating_avg or 0),
                    "instructor_description": user.instructor_description,
                    "wallet_balance": float(wallet_balance or 0),
                    "upgrade_date": upgrade_date,
                    "is_verified_email": user.is_verified_email,
                    "is_banned": user.is_banned,
                    "create_at": user.create_at,
                    "update_at": user.update_at,
                }
            )

        total_pages = (total_items + size - 1) // size

        return {
            "page": page,
            "size": size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "items": lecturers,
        }

    async def export_lecturers_async(self):
        """
        📘 Xuất danh sách giảng viên cùng thông tin thanh toán nâng cấp & ví.
        Bao gồm: thông tin cá nhân, ví, ngày nâng cấp, chi phí, giao dịch, v.v.
        """
        stmt = (
            select(
                User,
                Wallets.balance.label("wallet_balance"),
                LecturerUpgradePayments.amount.label("upgrade_amount"),
                LecturerUpgradePayments.paid_time.label("upgrade_date"),
                LecturerUpgradePayments.payment_status.label("payment_status"),
                Transactions.method.label("payment_method"),
                Transactions.transaction_code.label("transaction_code"),
                Transactions.status.label("transaction_status"),
                Transactions.created_at.label("transaction_created_at"),
            )
            .join(UserRoles, UserRoles.user_id == User.id)
            .join(Role, Role.id == UserRoles.role_id)
            .join(Wallets, Wallets.user_id == User.id, isouter=True)
            .join(
                LecturerUpgradePayments,
                LecturerUpgradePayments.user_id == User.id,
                isouter=True,
            )
            .join(
                Transactions,
                Transactions.id == LecturerUpgradePayments.transaction_id,
                isouter=True,
            )
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(
                Role.role_name == "LECTURER",
                Role.role_name != "ADMIN",
                User.deleted_at.is_(None),
            )
            .group_by(
                User.id,
                Wallets.balance,
                LecturerUpgradePayments.amount,
                LecturerUpgradePayments.paid_time,
                LecturerUpgradePayments.payment_status,
                Transactions.method,
                Transactions.transaction_code,
                Transactions.status,
                Transactions.created_at,
            )
        )

        result = await self.db.execute(stmt)
        records = result.fetchall()

        if not records:
            raise Exception("Không có giảng viên nào để xuất Excel")

        lecturers = []
        for (
            user,
            wallet_balance,
            upgrade_amount,
            upgrade_date,
            payment_status,
            payment_method,
            transaction_code,
            transaction_status,
            transaction_created_at,
        ) in records:
            lecturers.append(
                {
                    "Mã giảng viên": str(user.id),
                    "Họ tên": user.fullname,
                    "Email": user.email,
                    "CCCD": user.citizenship_identity,
                    "Ngày sinh": user.birthday,
                    "Địa chỉ": f"{user.district or ''}, {user.conscious or ''}",
                    "Ảnh đại diện": user.avatar,
                    "Bio": user.bio,
                    "Số khóa học": user.course_count or 0,
                    "Tổng học viên": user.student_count or 0,
                    "Số lượt đánh giá": user.evaluated_count or 0,
                    "Điểm trung bình": float(user.rating_avg or 0),
                    "Số dư ví (VNĐ)": float(wallet_balance or 0),
                    "Trạng thái Email": (
                        "✅ Đã xác minh"
                        if user.is_verified_email
                        else "❌ Chưa xác minh"
                    ),
                    "Bị cấm": "🚫 Có" if user.is_banned else "✅ Không",
                    # === DỮ LIỆU NÂNG CẤP GIẢNG VIÊN ===
                    "Ngày thanh toán nâng cấp": upgrade_date,
                    "Ngày đăng ký giao dịch": transaction_created_at,
                    "Mã giao dịch": transaction_code,
                    "Phương thức thanh toán": payment_method,
                    "Trạng thái giao dịch": transaction_status,
                    "Chi phí nâng cấp (VNĐ)": float(upgrade_amount or 0),
                    "Trạng thái thanh toán": payment_status,
                    "Ngày tạo tài khoản": user.create_at,
                }
            )

        # 🔹 Ghi Excel
        df = pd.DataFrame(lecturers)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="GiangVien", index=False)

        output.seek(0)

        headers = {
            "Content-Disposition": 'attachment; filename="lecturers_with_payments.xlsx"'
        }

        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    async def delete_lecture_async(
        self, admin: User, lecturer_id: uuid.UUID, reason: str
    ):
        try:
            # 🔹 Subquery: user chỉ có role "user" (hoặc chưa có role)
            only_user_subq = (
                select(UserRoles.user_id)
                .join(Role, Role.id == UserRoles.role_id)
                .group_by(UserRoles.user_id)
                .having(
                    func.max(Role.role_name) != "ADMIN",
                )
            )

            # 🔹 Lấy user hợp lệ
            user = await self.db.scalar(
                select(User).where(
                    User.id == lecturer_id,
                    or_(
                        User.id.in_(only_user_subq),
                        ~User.id.in_(select(UserRoles.user_id)),
                    ),
                )
            )

            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ có thể xóa giảng viên thường (user)",
                )

            if user.id == admin.id:
                raise HTTPException(
                    status_code=409,
                    detail="Không thể xóa tài khoản của chính mình",
                )

            user.deleted_at = await to_utc_naive(get_now())
            user.deleted_until = reason or "Không có lý do cụ thể"
            user.update_at = await to_utc_naive(get_now())

            await self.db.commit()
            await self.db.refresh(user)

            return {
                "message": "Xóa giảng viên thành công",
                "user_id": str(user.id),
                "deleted_at": user.deleted_at,
                "deleted_until": user.deleted_until,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa giảng viên: {e}")

    async def get_lecturer_detail_async(
        self,
        lecturer_id: str,
        page: int = 1,
        page_size: int = 5,
    ):
        """Lấy chi tiết giảng viên kèm phân trang giao dịch."""
        # 1️⃣ Thông tin giảng viên
        lecturer: User | None = await self.db.scalar(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(User.id == lecturer_id)
        )
        if not lecturer:
            raise HTTPException(404, "Không tìm thấy giảng viên")

        # 2️⃣ Ví
        wallet = await self.db.scalar(
            select(Wallets).where(Wallets.user_id == lecturer_id)
        )

        # 3️⃣ Nâng cấp
        upgrade = await self.db.scalar(
            select(LecturerUpgradePayments).where(
                LecturerUpgradePayments.user_id == lecturer_id
            )
        )

        # 4️⃣ Giao dịch (phân trang + sắp xếp)
        offset = (page - 1) * page_size
        tx_query = (
            select(Transactions)
            .where(Transactions.user_id == lecturer_id)
            .order_by(desc(Transactions.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result_tx = await self.db.execute(tx_query)
        transactions = result_tx.scalars().all()

        # 5️⃣ Tổng số giao dịch để tính tổng trang
        total_tx = await self.db.scalar(
            select(func.count()).select_from(
                select(Transactions.id)
                .where(Transactions.user_id == lecturer_id)
                .subquery()
            )
        )

        # 6️⃣ Chuẩn hóa trả về
        return {
            "id": str(lecturer.id),
            "fullname": lecturer.fullname,
            "email": lecturer.email,
            "avatar": lecturer.avatar,
            "bio": lecturer.bio,
            "is_banned": lecturer.is_banned,
            "banned_reason": lecturer.banned_reason,
            "banned_until": lecturer.banned_until,
            "citizenship_identity": lecturer.citizenship_identity,
            "birthday": lecturer.birthday,
            "conscious": lecturer.conscious,
            "district": lecturer.district,
            "course_count": lecturer.course_count,
            "student_count": lecturer.student_count,
            "evaluated_count": lecturer.evaluated_count,
            "rating_avg": round(float(lecturer.rating_avg or 0), 2),
            "instructor_description": lecturer.instructor_description,
            "create_at": lecturer.create_at,
            "update_at": lecturer.update_at,
            "is_verified_email": lecturer.is_verified_email,
            "wallet": {
                "balance": round(float(wallet.balance or 0), 2) if wallet else 0,
                "total_in": round(float(wallet.total_in or 0), 2) if wallet else 0,
                "total_out": round(float(wallet.total_out or 0), 2) if wallet else 0,
                "last_transaction_at": wallet.last_transaction_at if wallet else None,
            },
            "upgrade_payment": {
                "amount": round(float(upgrade.amount or 0), 2) if upgrade else 0,
                "paid_time": upgrade.paid_time if upgrade else None,
                "payment_status": upgrade.payment_status if upgrade else None,
                "verified_by": (
                    str(upgrade.verified_by)
                    if upgrade and upgrade.verified_by
                    else None
                ),
                "note": upgrade.note if upgrade else None,
            },
            "transactions": [
                {
                    "id": str(tx.id),
                    "amount": round(float(tx.amount), 2),
                    "type": tx.type,
                    "method": tx.method,
                    "status": tx.status,
                    "transaction_code": tx.transaction_code,
                    "description": tx.description,
                    "created_at": tx.created_at,
                    "confirmed_at": tx.confirmed_at,
                }
                for tx in transactions
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_tx or 0,
                "total_pages": (
                    (total_tx + page_size - 1) // page_size if total_tx else 0
                ),
            },
        }

    # -------------------------------
    # 2️⃣ Hàm phụ: phân trang & sắp xếp khóa học
    # -------------------------------
    async def get_lecturer_courses_async(
        self,
        lecturer_id: str,
        page: int = 1,
        size: int = 5,
        sort_by: str = "created_at",
        order: str = "desc",
    ):
        """Phân trang + sắp xếp danh sách khóa học của giảng viên."""

        # kiểm tra giảng viên có tồn tại
        exists = await self.db.scalar(
            select(func.count()).select_from(User).where(User.id == lecturer_id)
        )
        if not exists:
            raise HTTPException(404, "Giảng viên không tồn tại")

        # danh sách cột hợp lệ để sắp xếp
        allowed_sort_fields = {
            "title": Courses.title,
            "views": Courses.views,
            "price": Courses.base_price,
            "total_enrolls": Courses.total_enrolls,
            "total_reviews": Courses.total_reviews,
            "rating": Courses.rating_avg,
            "created_at": Courses.created_at,
            "updated_at": Courses.updated_at,
        }
        sort_column = allowed_sort_fields.get(sort_by, Courses.created_at)
        sort_direction = desc if order.lower() == "desc" else asc

        # tổng số khóa học
        total_courses = await self.db.scalar(
            select(func.count())
            .select_from(Courses)
            .where(Courses.instructor_id == lecturer_id)
        )
        total_pages = (total_courses + size - 1) // size
        offset = (page - 1) * size

        # truy vấn dữ liệu
        result_courses = await self.db.execute(
            select(Courses)
            .options(
                selectinload(Courses.course_sections).selectinload(
                    CourseSections.lessons
                )
            )
            .where(Courses.instructor_id == lecturer_id)
            .order_by(sort_direction(sort_column))
            .offset(offset)
            .limit(size)
        )
        courses = result_courses.scalars().all()

        # trả về cấu trúc phân trang chuẩn
        return {
            "page": page,
            "size": size,
            "total_items": total_courses,
            "total_pages": total_pages,
            "sort_by": sort_by,
            "order": order,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "items": [
                {
                    "id": str(course.id),
                    "title": course.title,
                    "slug": course.slug,
                    "thumbnail": course.thumbnail_url,
                    "description": course.description,
                    "price": float(course.base_price or 0),
                    "rating_avg": float(course.rating_avg or 0),
                    "rating_count": float(course.rating_count or 0),
                    "total_reviews": float(course.total_reviews or 0),
                    "total_enrolls": course.total_enrolls or 0,
                    "views": course.views or 0,
                    "language": course.language,
                    "level": course.level,
                    "is_published": course.is_published,
                    "created_at": course.created_at,
                    "updated_at": course.updated_at,
                    "sections": [
                        {
                            "id": str(section.id),
                            "title": section.title,
                            "position": section.position,
                            "lessons": [
                                {
                                    "id": str(lesson.id),
                                    "title": lesson.title,
                                    "lesson_type": lesson.lesson_type,
                                    "position": lesson.position,
                                }
                                for lesson in section.lessons
                            ],
                        }
                        for section in course.course_sections
                    ],
                }
                for course in courses
            ],
        }

    async def ban_lecturer_async(self, admin: User, lecturer_id: uuid.UUID, schema):
        """Chặn giảng viên (role = 'LECTURER')."""
        try:
            # 1️⃣ Subquery: chỉ lấy user có role 'LECTURER'
            lecturer_subq = (
                select(UserRoles.user_id)
                .join(Role, Role.id == UserRoles.role_id)
                .group_by(UserRoles.user_id)
                .having(func.max(Role.role_name) == "LECTURER")
            )

            # 2️⃣ Lấy giảng viên hợp lệ
            lecturer = await self.db.scalar(
                select(User).where(
                    User.id == lecturer_id,
                    User.id.in_(lecturer_subq),
                )
            )

            if not lecturer:
                raise HTTPException(
                    403, "Chỉ được chặn người có vai trò giảng viên (lecturer)."
                )

            if lecturer.id == admin.id:
                raise HTTPException(409, "Không thể tự chặn chính mình.")

            if lecturer.is_banned:
                raise HTTPException(409, "Giảng viên đang trong thời gian bị chặn.")

            # 3️⃣ Thực hiện chặn
            lecturer.is_banned = True
            lecturer.banned_reason = schema.banned_reason
            lecturer.banned_until = (
                None
                if schema.is_block_permanently
                else to_utc_naive(schema.banned_until or get_now())
            )
            lecturer.update_at = get_now()

            await self.db.commit()
            await self.db.refresh(lecturer)
            return {"message": "Đã chặn giảng viên thành công."}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi chặn giảng viên: {e}")

    async def unlock_ban_lecturer_async(self, admin: User, lecturer_id: uuid.UUID):
        """Gỡ chặn giảng viên."""
        try:
            # 1️⃣ Subquery: chỉ lấy user có role 'LECTURER'
            lecturer_subq = (
                select(UserRoles.user_id)
                .join(Role, Role.id == UserRoles.role_id)
                .group_by(UserRoles.user_id)
                .having(func.max(Role.role_name) == "LECTURER")
            )

            # 2️⃣ Lấy giảng viên hợp lệ
            lecturer = await self.db.scalar(
                select(User).where(
                    User.id == lecturer_id,
                    User.id.in_(lecturer_subq),
                )
            )

            if not lecturer:
                raise HTTPException(403, "Chỉ được mở chặn giảng viên.")

            if lecturer.id == admin.id:
                raise HTTPException(409, "Không thể tự mở chặn chính mình.")

            if not lecturer.is_banned:
                raise HTTPException(409, "Giảng viên chưa từng bị chặn.")

            # 3️⃣ Gỡ chặn
            lecturer.is_banned = False
            lecturer.banned_reason = None
            lecturer.banned_until = None
            lecturer.update_at = get_now()

            await self.db.commit()
            await self.db.refresh(lecturer)
            return {"message": "Đã mở chặn giảng viên thành công."}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi mở chặn giảng viên: {e}")

    async def remove_instructor_rights_async(
        self,
        admin: User,
        lecturer_id: uuid.UUID,
    ):
        """Gỡ quyền giảng viên (LECTURER) của user."""
        try:
            # 1️⃣ Kiểm tra user có đúng role LECTURER không
            user_role = await self.db.scalar(
                select(UserRoles)
                .join(Role, Role.id == UserRoles.role_id)
                .where(UserRoles.user_id == lecturer_id, Role.role_name == "LECTURER")
            )

            if not user_role:
                raise HTTPException(403, "Chỉ được gỡ quyền giảng viên (LECTURER).")

            if lecturer_id == admin.id:
                raise HTTPException(
                    409, "Không thể tự gỡ quyền giảng viên của chính mình."
                )

            # 2️⃣ Thực hiện xóa quyền giảng viên
            await self.db.execute(
                delete(UserRoles).where(
                    UserRoles.user_id == lecturer_id,
                    UserRoles.role_id == user_role.role_id,
                )
            )

            await self.db.commit()
            return {"message": "Đã gỡ quyền giảng viên thành công."}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi gỡ quyền giảng viên: {e}")

    async def add_instructor_rights_async(
        self,
        admin: User,
        user_id: uuid.UUID,
    ):
        """Cấp quyền giảng viên (LECTURER) cho user."""
        try:
            # 1️⃣ Kiểm tra user tồn tại
            user = await self.db.scalar(select(User).where(User.id == user_id))
            if not user:
                raise HTTPException(404, "Không tìm thấy người dùng cần cấp quyền.")

            if user.id == admin.id:
                raise HTTPException(409, "Không thể tự cấp quyền cho chính mình.")

            # 2️⃣ Lấy role giảng viên
            lecturer_role = await self.db.scalar(
                select(Role).where(Role.role_name == "LECTURER")
            )
            if not lecturer_role:
                raise HTTPException(
                    404, "Không tìm thấy role 'LECTURER' trong hệ thống."
                )

            # 3️⃣ Kiểm tra user đã có role giảng viên chưa
            has_role = await self.db.scalar(
                select(UserRoles).where(
                    UserRoles.user_id == user_id,
                    UserRoles.role_id == lecturer_role.id,
                )
            )
            if has_role:
                raise HTTPException(409, "Người dùng này đã là giảng viên.")

            # 4️⃣ Thêm quyền giảng viên
            await self.db.execute(
                insert(UserRoles).values(
                    user_id=user_id,
                    role_id=lecturer_role.id,
                    create_at=await to_utc_naive(get_now()),
                    update_at=await to_utc_naive(get_now()),
                )
            )
            await self.db.commit()

            return {"message": "Đã cấp quyền giảng viên thành công."}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi cấp quyền giảng viên: {e}")
