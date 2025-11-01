# app/services/admin/role_service.py
import uuid
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import Depends, HTTPException, Response
from sqlalchemy import asc, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import Role, User, UserRoles
from app.db.sesson import get_session
from app.schemas.admin.role import CreateRole, UpadteRole


class RoleService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_roles_async(
        self, search: str | None, sort_by: str, order: str, page: int, size: int
    ):
        try:
            stmt = (
                select(Role, func.count(User.id).label("total_users"))
                .join(UserRoles, UserRoles.role_id == Role.id, isouter=True)
                .join(User, User.id == UserRoles.user_id, isouter=True)
                .where(User.deleted_at.is_(None))
                .group_by(Role.id)
            )

            if search:
                stmt = stmt.where(
                    or_(
                        Role.role_name.ilike(f"%{search}%"),
                        Role.details.ilike(f"%{search}%"),
                    )
                )

            subq = stmt.subquery()
            total_items = (
                await self.db.scalar(select(func.count()).select_from(subq)) or 0
            )
            operational_roles = (
                await self.db.scalar(
                    select(func.count()).select_from(subq).where(subq.c.total_users > 0)
                )
            ) or 0

            if total_items == 0:
                return {
                    "page": page,
                    "size": size,
                    "total_items": 0,
                    "total_pages": 0,
                    "operational_roles": 0,
                    "items": [],
                }

            if sort_by == "total_users":
                sort_expr = (
                    desc("total_users")
                    if order.lower() == "desc"
                    else asc("total_users")
                )
            else:
                sort_col = getattr(Role, sort_by, Role.role_name)
                sort_expr = (
                    sort_col.desc() if order.lower() == "desc" else sort_col.asc()
                )

            stmt = stmt.order_by(sort_expr)
            stmt = stmt.offset((page - 1) * size).limit(size)
            result = await self.db.execute(stmt)
            records = result.fetchall()

            items = [
                {
                    "id": str(role.id),
                    "role_name": role.role_name,
                    "details": role.details,
                    "total_users": total_users or 0,
                }
                for role, total_users in records
            ]

            total_pages = (total_items + size - 1) // size
            return {
                "page": page,
                "size": size,
                "total_items": total_items,
                "total_pages": total_pages,
                "operational_roles": operational_roles,
                "has_next": page < total_pages,
                "has_previous": page > 1,
                "items": items,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy danh sách quyền: {e}")

    async def export_roles_async(self, search: Optional[str], sort_by: str, order: str):
        stmt = (
            select(Role, func.count(User.id).label("total_users"))
            .join(UserRoles, UserRoles.role_id == Role.id, isouter=True)
            .join(User, User.id == UserRoles.user_id, isouter=True)
            .group_by(Role.id)
        )
        if search:
            stmt = stmt.where(
                or_(
                    Role.role_name.ilike(f"%{search}%"),
                    Role.details.ilike(f"%{search}%"),
                )
            )

        if sort_by == "total_users":
            sort_expr = (
                desc("total_users") if order.lower() == "desc" else asc("total_users")
            )
        else:
            sort_col = getattr(Role, sort_by, Role.role_name)
            sort_expr = sort_col.asc() if order.lower() == "asc" else sort_col.desc()
        stmt = stmt.order_by(sort_expr)

        result = await self.db.execute(stmt)
        records = result.all()

        items = [
            {
                "Mã quyền hạn": str(role.id),
                "Quyền hạn": role.role_name,
                "Chi tiết": role.details,
                "Tổng số người dùng": total_users or 0,
            }
            for role, total_users in records
        ]
        df = pd.DataFrame(
            items,
            columns=["Mã quyền hạn", "Quyền hạn", "Chi tiết", "Tổng số người dùng"],
        )
        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        headers = {"Content-Disposition": "attachment; filename=roles_export.xlsx"}
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    async def create_role_async(self, schema: CreateRole):
        try:
            role = await self.db.scalar(
                select(Role).where(Role.role_name == schema.role_name)
            )
            if role:
                raise HTTPException(409, "Role already exists")
            new_role = Role(**schema.model_dump())
            self.db.add(new_role)
            await self.db.commit()
            return {"message": "Role created", "role": new_role}
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo role: {e}")

    async def delete_role_async(self, role_id: uuid.UUID):
        try:
            in_use = await self.db.scalar(
                select(UserRoles).where(UserRoles.role_id == role_id)
            )
            if in_use:
                raise HTTPException(
                    409, "Không thể xóa role vì đang có người dùng gắn với role này."
                )
            await self.db.execute(delete(Role).where(Role.id == role_id))
            await self.db.commit()
            return {"message": "Role deleted"}
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi xóa role: {e}")

    async def update_role_async(self, role_id: uuid.UUID, schema: UpadteRole):
        try:
            role = await self.db.scalar(select(Role).where(Role.id == role_id))
            if not role:
                raise HTTPException(404, "Role not found")
            if schema.role_name:
                role.role_name = schema.role_name
            if schema.details:
                role.details = schema.details
            await self.db.commit()
            return {"message": "Role updated", "role": role}
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi cập nhật role: {e}")
