import uuid
from datetime import datetime
from io import BytesIO
from operator import and_
from typing import Optional

import pandas as pd
from fastapi import Depends, HTTPException, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.database import CourseEnrollments, Role, User, UserRoles
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now, to_utc_naive
from app.schemas.auth.user import BlockUser, EditUser


class UserService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_users_async(
        self,
        is_verified_email: bool | None,
        is_banned: bool | None,
        search: str | None,
        sort_by: str,
        order: str,
        page: int,
        size: int,
    ):
        # 🔹 Subquery: user chỉ có role duy nhất là "USER"
        only_user_subq = (
            select(UserRoles.user_id)
            .join(Role, Role.id == UserRoles.role_id)
            .group_by(UserRoles.user_id)
            .having(
                and_(
                    func.count(func.distinct(Role.role_name)) == 1,
                    func.max(Role.role_name) == "USER",
                )
            )
        )

        # 🔹 Main query
        stmt = (
            select(User, func.count(CourseEnrollments.id).label("enroll_count"))
            .join(CourseEnrollments, CourseEnrollments.user_id == User.id, isouter=True)
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(
                User.deleted_at.is_(None),  # chỉ lấy user chưa xóa
                or_(
                    User.id.in_(only_user_subq),  # chỉ có role "USER"
                    ~User.id.in_(select(UserRoles.user_id)),  # không có role nào
                ),
            )
            .group_by(User.id)
        )

        # 2️⃣ Lọc thêm
        if is_verified_email is not None:
            stmt = stmt.where(User.is_verified_email.is_(is_verified_email))
        if is_banned is not None:
            stmt = stmt.where(User.is_banned.is_(is_banned))
        if search:
            stmt = stmt.where(
                or_(
                    User.fullname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )

        # 3️⃣ Đếm tổng
        subquery = stmt.subquery()
        total_items = (
            await self.db.scalar(select(func.count()).select_from(subquery)) or 0
        )

        # 4️⃣ Phân trang
        sort_column = getattr(User, sort_by, None) or User.create_at
        sort_expr = sort_column.asc() if order.lower() == "asc" else sort_column.desc()
        stmt = stmt.order_by(sort_expr).offset((page - 1) * size).limit(size)

        # 5️⃣ Query
        result = await self.db.execute(stmt)
        records = result.all()

        users = [
            {
                "id": user.id,
                "fullname": user.fullname,
                "email": user.email,
                "created_at": user.create_at,
                "updated_at": user.update_at,
                "is_verified_email": user.is_verified_email,
                "total_courses": total_courses,
                "last_login_at": user.last_login_at,
                "is_banned": user.is_banned,
            }
            for user, total_courses in records
        ]

        total_pages = (total_items + size - 1) // size

        return {
            "page": page,
            "size": size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "items": users,
        }

    async def export_user_async(self):
        # 🔹 Subquery: user chỉ có role duy nhất là "USER"
        only_user_subq = (
            select(UserRoles.user_id)
            .join(Role, Role.id == UserRoles.role_id)
            .group_by(UserRoles.user_id)
            .having(
                func.max(Role.role_name) != "ADMIN",
            )
        )

        # 🔹 Main query: chỉ lấy user không có role hoặc chỉ có role user
        stmt = (
            select(User, func.count(CourseEnrollments.id).label("enroll_count"))
            .join(CourseEnrollments, CourseEnrollments.user_id == User.id, isouter=True)
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(
                and_(
                    User.deleted_at.is_(None),  # chỉ lấy user chưa xóa
                    or_(
                        User.id.in_(only_user_subq),  # chỉ có role user
                        ~User.id.in_(select(UserRoles.user_id)),  # không có role nào
                    ),
                )
            )
            .group_by(User.id)
        )

        # 🔹 Thực thi
        result = await self.db.execute(stmt)
        records = result.fetchall()

        # 🔹 Map dữ liệu
        users = []
        for user, total_courses in records:
            roles = [ur.role.role_name for ur in user.user_roles if ur and ur.role]
            roles_str = ", ".join(roles) if roles else "—"
            users.append(
                {
                    "Mã người dùng": user.id,
                    "Căn cước công dân": user.citizenship_identity,
                    "Họ Tên": user.fullname,
                    "Email": user.email,
                    "Ngày Tạo": user.create_at,
                    "Quyền Hạn": roles_str,
                    "Xác thực Email": user.is_verified_email,
                    "Tổng số khóa học người dùng đăng ký": total_courses,
                    "Lần cuối đăng nhập": user.last_login_at,
                    "Cấm": user.is_banned,
                }
            )

        # 🔹 Xuất Excel
        df = pd.DataFrame(
            users,
            columns=[
                "Mã người dùng",
                "Căn cước công dân",
                "Họ Tên",
                "Email",
                "Ngày Tạo",
                "Quyền Hạn",
                "Xác thực Email",
                "Tổng số khóa học người dùng đăng ký",
                "Lần cuối đăng nhập",
                "Cấm",
            ],
        )

        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        headers = {"Content-Disposition": "attachment; filename=user_export.xlsx"}

        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    async def update_user_async(
        self, schema: EditUser, admin: User, user_id: uuid.UUID
    ):
        try:

            only_user_subq = (
                select(UserRoles.user_id)
                .join(Role, Role.id == UserRoles.role_id)
                .group_by(UserRoles.user_id)
                .having(
                    func.max(Role.role_name) != "ADMIN",
                )
            )

            # 🔹 Lấy user cần cập nhật
            user = await self.db.scalar(
                select(User).where(
                    User.id == user_id,
                    User.deleted_at.is_(None),
                    or_(
                        User.id.in_(only_user_subq),  # chỉ có role user
                        ~User.id.in_(select(UserRoles.user_id)),  # không có role nào
                    ),
                )
            )

            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ có thể sửa người dùng thông thường (user)",
                )

            # 🔹 Cập nhật thông tin
            if schema.fullname:
                user.fullname = schema.fullname

            if schema.email:
                existing_user = await self.db.scalar(
                    select(User).where(User.email == schema.email, User.id != user_id)
                )
                if existing_user:
                    raise HTTPException(status_code=409, detail="Email đã được sử dụng")
                user.email = schema.email

            user.update_at = get_now()
            await self.db.commit()
            await self.db.refresh(user)
            return {"message": "Cập nhật người dùng thành công"}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi cập nhật người dùng: {e}"
            )

    async def get_user_by_id_async(self, user_id: uuid.UUID):
        try:
            # 1️⃣ Lấy user + role
            user: User | None = await self.db.scalar(
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            )

            if user is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

            # 2️⃣ Danh sách quyền
            roles = [ur.role.role_name for ur in user.user_roles if ur.role is not None]

            # 3️⃣ Cấu trúc trả về dạng chuẩn dashboard
            return {
                "profile": {
                    "id": user.id,
                    "fullname": user.fullname,
                    "email": user.email,
                    "avatar": user.avatar,
                    "birthday": user.birthday,
                    "created_at": user.create_at,
                    "updated_at": user.update_at,
                },
                "status": {
                    "is_verified_email": user.is_verified_email,
                    "email_verified_at": user.email_verified_at,
                    "is_banned": user.is_banned,
                    "banned_reason": user.banned_reason,
                    "banned_until": user.banned_until,
                    "last_login_at": user.last_login_at,
                    "deleted_at": user.deleted_at,
                    "deleted_until": user.deleted_until,
                },
                "roles": roles,
                "statistics": {
                    "total_courses_enrolled": 0,
                    "total_courses_completed": 0,
                    "average_progress": 0.0,
                },
                "transactions": {
                    "total_spent": 0,
                    "currency": "VND",
                    "last_payment_at": None,
                },
                "recent_activity": {
                    "last_watched_course": None,
                    "last_watched_time": None,
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi lấy thông tin người dùng: {e}"
            )

    async def ban_user_async(self, admin: User, user_id: uuid.UUID, schema: BlockUser):
        try:
            # 🔹 Subquery: user chỉ có role "USER" hoặc không có role
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
                    User.id == user_id,
                    or_(
                        User.id.in_(only_user_subq),
                        ~User.id.in_(select(UserRoles.user_id)),
                    ),
                )
            )

            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ được chặn người dùng thường (user)",
                )

            if user.id == admin.id:
                raise HTTPException(status_code=409, detail="Không thể ban chính mình")

            if user.is_banned:
                raise HTTPException(
                    status_code=409, detail="Người dùng đang trong thời gian bị chặn"
                )

            # 🔹 Ban user
            user.is_banned = True
            user.banned_reason = schema.banned_reason
            if schema.is_block_permanently:
                user.banned_until = None
            else:
                user.banned_until = to_utc_naive(
                    schema.banned_until or get_now()
                )
            user.update_at = to_utc_naive(schema.banned_until or get_now())

            await self.db.commit()
            await self.db.refresh(user)
            return {"message": "Đã chặn người dùng thành công"}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi chặn người dùng: {e}")

    async def unlock_ban_user_async(self, admin: User, user_id: uuid.UUID):
        try:
            # 🔹 Subquery: user chỉ có role "USER" hoặc không có role
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
                    User.id == user_id,
                    or_(
                        User.id.in_(only_user_subq),
                        ~User.id.in_(select(UserRoles.user_id)),
                    ),
                )
            )

            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ được mở chặn người dùng thường (user)",
                )

            if user.id == admin.id:
                raise HTTPException(
                    status_code=409, detail="Không thể tự unban chính mình"
                )

            if not user.is_banned:
                raise HTTPException(
                    status_code=409, detail="Người dùng chưa từng bị chặn"
                )

            # 🔹 Gỡ chặn user
            user.is_banned = False
            user.banned_reason = None
            user.banned_until = None
            user.update_at = get_now()

            await self.db.commit()
            await self.db.refresh(user)
            return {"message": "Đã mở chặn người dùng thành công"}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi mở chặn người dùng: {e}"
            )

    async def get_users_deleted_async(
        self,
        search: Optional[str],
        is_verified_email: Optional[bool],
        sort_by: str,
        order: str,
        page: int,
        size: int,
    ):
        # 🔹 Subquery: chỉ user có đúng 1 role là 'user'
        only_user_subq = (
            select(UserRoles.user_id)
            .join(Role, Role.id == UserRoles.role_id)
            .group_by(UserRoles.user_id)
            .having(
                func.max(Role.role_name) != "ADMIN",
            )
        )

        # 🔹 Base query: user đã bị xóa, chỉ lấy user thường hoặc chưa có role
        stmt = (
            select(User, func.count(CourseEnrollments.id).label("enroll_count"))
            .join(CourseEnrollments, CourseEnrollments.user_id == User.id, isouter=True)
            .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            .where(
                and_(
                    User.deleted_at.is_not(None),
                    or_(
                        User.id.in_(only_user_subq),
                        ~User.id.in_(select(UserRoles.user_id)),
                    ),
                )
            )
            .group_by(User.id)
        )

        # 🔹 Lọc tìm kiếm
        if search:
            stmt = stmt.where(
                or_(
                    User.fullname.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )

        # 🔹 Lọc xác thực email
        if is_verified_email is not None:
            stmt = stmt.where(User.is_verified_email.is_(is_verified_email))

        # 🔹 Đếm tổng user đã xóa (theo điều kiện)
        subquery = stmt.subquery()
        total_items = (
            await self.db.scalar(select(func.count()).select_from(subquery)) or 0
        )

        # 🔹 Tổng số khóa học của user đã xóa
        total_courses_all_users = (
            await self.db.scalar(
                select(func.count(CourseEnrollments.id))
                .join(User, CourseEnrollments.user_id == User.id)
                .where(User.deleted_at.is_not(None))
            )
            or 0
        )

        # 🔹 Nếu không có user
        if total_items == 0:
            return {
                "total_items": 0,
                "total_pages": 0,
                "page": page,
                "size": size,
                "items": [],
                "total_courses_all_users": 0,
            }

        # 🔹 Phân trang & sắp xếp
        sort_column = getattr(User, sort_by, User.create_at)
        sort_expr = sort_column.asc() if order.lower() == "asc" else sort_column.desc()
        stmt = stmt.order_by(sort_expr).offset((page - 1) * size).limit(size)

        result = await self.db.execute(stmt)
        records = result.all()

        # 🔹 Map kết quả
        users = []
        for user, total_courses in records:
            roles = [ur.role.role_name for ur in user.user_roles if ur and ur.role]
            users.append(
                {
                    "id": user.id,
                    "fullname": user.fullname,
                    "email": user.email,
                    "created_at": user.create_at,
                    "roles": roles,
                    "is_verified_email": user.is_verified_email,
                    "total_courses": total_courses,
                    "deleted_at": user.deleted_at,
                    "deleted_until": user.deleted_until,
                }
            )

        total_pages = (total_items + size - 1) // size

        return {
            "page": page,
            "size": size,
            "total_items": total_items,
            "total_pages": total_pages,
            "total_courses_all_users": total_courses_all_users,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "items": users,
        }

    async def delete_user_async(self, admin: User, user_id: uuid.UUID, reason: str):
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
                    User.id == user_id,
                    or_(
                        User.id.in_(only_user_subq),
                        ~User.id.in_(select(UserRoles.user_id)),
                    ),
                )
            )

            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="Chỉ có thể xóa người dùng thường (user)",
                )

            if user.id == admin.id:
                raise HTTPException(
                    status_code=409,
                    detail="Không thể xóa tài khoản của chính mình",
                )

            # 🔹 Ghi nhận thời gian và lý do xóa
            user.deleted_at = get_now()
            user.deleted_until = reason or "Không có lý do cụ thể"
            user.update_at = get_now()

            await self.db.commit()
            await self.db.refresh(user)

            return {
                "message": "Xóa người dùng thành công",
                "user_id": str(user.id),
                "deleted_at": user.deleted_at,
                "deleted_until": user.deleted_until,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa người dùng: {e}")
