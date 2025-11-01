# app/core/auth_service.py
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.context import get_request
from app.core.security import SecurityService
from app.db.models.database import User, UserRoles
from app.db.sesson import get_session


class AuthorizationService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        security: SecurityService = Depends(SecurityService),
    ):
        self.db = db
        self.security = security

    # ==============================
    # 🧩 CORE AUTH CHECKS
    # ==============================

    async def get_current_user(self) -> User:
        """Lấy user hiện tại từ cookie access_token."""
        request = get_request()  # ✅ Lấy đúng thời điểm đang có request
        token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(status_code=401, detail="Token not found in cookies")

        try:
            dict_token = self.security.decode_access_token(token)
            user_id = dict_token.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")

            stmt = (
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            )
            user = await self.db.scalar(stmt)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid token")

            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)
            return user

        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    async def get_current_user_if_any(self) -> Optional[User]:
        """Lấy user nếu có (nếu chưa login thì trả None)."""
        try:
            request = get_request()
            token = request.cookies.get("access_token")
            if not token:
                return None

            dict_token = self.security.decode_access_token(token)
            user_id = dict_token.get("sub")
            if not user_id:
                return None

            stmt = (
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            )
            user = await self.db.scalar(stmt)
            if not user:
                return None

            user.last_login_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)
            return user

        except Exception:
            return None

    # ==============================
    # 🧩 ROLE-BASED ACCESS CONTROL
    # ==============================

    async def require_role(self, required_roles: Optional[List[str]] = None) -> User:
        """Yêu cầu user có quyền cụ thể (vd: ADMIN)."""
        current_user = await self.get_current_user()

        if not required_roles:
            return current_user

        user_roles = [ur.role.role_name for ur in current_user.user_roles if ur.role]
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(status_code=403, detail="Permission denied")

        return current_user
