# app/core/auth_service.py
from functools import lru_cache
from typing import List, Optional

from fastapi import Depends, HTTPException, WebSocket
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.context import get_request
from app.core.security import SecurityService
from app.db.models.database import User, UserRoles
from app.db.sesson import AsyncSessionLocal, get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_utc_naive


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
            dict_token = await self.security.decode_access_token(token)
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

            user.last_login_at = await to_utc_naive(get_now())
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

            dict_token = await self.security.decode_access_token(token)
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

            user.last_login_at = await to_utc_naive(get_now())
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

    @staticmethod
    async def get_list_role_in_user(user: User):
        try:
            user_roles = [ur.role.role_name for ur in user.user_roles if ur.role]
            return user_roles
        except Exception as e:
            raise e

    @staticmethod
    async def get_require_role_ws(
        websocket: WebSocket,
        required_roles: Optional[list[str]] = None,
    ) -> User | None:
        """
        Lấy user từ WebSocket:
        - Ưu tiên query param: ?token= hoặc ?access_token=
        - Sau đó Authorization header của handshake
        - Sau đó cookie access_token (nếu có)
        - Nếu lỗi → gửi thông báo lỗi và đóng kết nối.
        """

        token = (
            websocket.query_params.get("token")
            or websocket.query_params.get("access_token")
            or websocket.headers.get("authorization")
            or websocket.cookies.get("access_token")
        )

        if token and token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip()

        if not token:
            await websocket.send_json({"error": "Thiếu token xác thực"})
            await websocket.close(code=1008)
            return None

        try:
            # ✅ Decode token
            async with SecurityService() as security:
                payload = await security.decode_access_token(token)

            user_id = payload.get("sub")
            if not user_id:
                await websocket.send_json({"error": "Token không hợp lệ"})
                await websocket.close(code=1008)
                return None

            # ✅ Query user
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(User)
                    .where(User.id == user_id)
                    .options(selectinload(User.user_roles).selectinload(UserRoles.role))
                )
                user = await db.scalar(stmt)
                if not user:
                    await websocket.send_json({"error": "User không tồn tại"})
                    await websocket.close(code=1008)
                    return None
                # ✅ Kiểm tra quyền
                if required_roles:
                    user_roles = [
                        ur.role.role_name for ur in user.user_roles if ur.role
                    ]
                    if not any(r in user_roles for r in required_roles):
                        await websocket.send_json({"error": "Permission denied"})
                        await websocket.close(code=1008)
                        return None

                return user

        except Exception as e:
            await websocket.send_json(
                {"error": f"Token không hợp lệ hoặc đã hết hạn ({str(e)})"}
            )
            await websocket.close(code=1008)
            return None


@lru_cache(maxsize=1)
def get_authorization_service() -> AuthorizationService:
    """
    Singleton GoogleDriveAsyncService — chỉ khởi tạo 1 lần duy nhất trong suốt vòng đời app.
    Dùng cho FastAPI: google_drive: GoogleDriveAsyncService = Depends(get_google_drive_service)
    """
    logger.info(
        "🚀 get_google_drive_service() gọi lần đầu → tạo GoogleDriveAsyncService singleton"
    )
    return AuthorizationService()
