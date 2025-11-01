from __future__ import annotations

from datetime import datetime, timedelta
from re import DEBUG
from typing import Any

from fastapi import Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc

from app.core.security import SecurityService
from app.db.models.database import EmailVerifications, Role, User, UserRoles
from app.db.sesson import get_session
from app.schemas.auth.user import LoginUser, RefreshEmail, UserCreate, VerifyEmail
from app.services.shares.mailer import MailerService


class AuthService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        security: SecurityService = Depends(SecurityService),
        mail_service: MailerService = Depends(MailerService),
    ):
        self.db = db
        self.security = security
        self.mail_service = mail_service

    async def login_async(self, schema: LoginUser, res: Response):
        try:
            stmt = (
                select(User)
                .where(User.email == schema.email)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            )
            result = await self.db.execute(stmt)
            user: User | None = result.scalar()
            if not user:
                raise HTTPException(404, "User not found")
            if not self.security.verify_password(schema.password, user.password or ""):
                raise HTTPException(404, "User not found")
            if not user.is_verified_email:
                raise HTTPException(401, "Người dùng chưa xác thực email")

            if user.is_banned:
                if user.banned_until and user.banned_until < datetime.utcnow():
                    user.is_banned = False
                    user.banned_reason = None
                    user.banned_until = None
                    await self.db.commit()
                else:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Tài khoản bị khóa: {user.banned_reason or 'Không rõ lý do'}",
                    )

            res.set_cookie(
                key="access_token",
                value=self.security.create_access_token(str(user.id)),
                httponly=True,
                secure=not DEBUG,  # 🟢 Dev = False, Prod = True
                samesite="lax",  # hoặc "none" nếu frontend/backend khác domain
                max_age=60 * 60 * 24,
                path="/",
            )
            return {"message": "Login successful"}
        except Exception:
            await self.db.rollback()
            raise

    async def register_async(self, schema: UserCreate) -> dict[str, Any]:
        try:
            existing_id = (
                await self.db.scalars(select(User.id).where(User.email == schema.email))
            ).first()
            if existing_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            new_user = User()
            new_user.email = schema.email
            new_user.fullname = schema.full_name if schema.full_name else ""
            password_hash = self.security.hash_password(schema.password)
            new_user.is_active = False
            new_user.password = password_hash
            new_user.create_at = datetime.utcnow()
            self.db.add(new_user)
            await self.db.flush()
            code = self.security.generate_otp()
            expired_at = datetime.utcnow() + timedelta(minutes=5)
            verification = EmailVerifications(
                user_id=new_user.id, code=code, expired_at=expired_at
            )
            self.db.add(verification)
            await self.db.commit()
            await self.db.refresh(new_user)
            await self.mail_service.send_verification_email(
                schema.email, schema.full_name or "", code
            )
            return {"message": "send Email ok"}
        except Exception:
            await self.db.rollback()
            raise

    async def logout_async(self, res: Response):
        res.delete_cookie(
            key="access_token",
            httponly=True,
            secure=False,  # dev: False (chạy https thì True)
            samesite=None,  # 👈 cho cross-site (FE:3000 <-> BE:8000)
            path="/",
            domain=None,
        )
        return "Logout done"

    async def refesh_email_async(self, schema: RefreshEmail):
        try:
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            tomorrow_start = today_start + timedelta(days=1)
            user = (
                await self.db.scalars(select(User).where((User.email == schema.email)))
            ).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )
            if user.is_verified_email == True:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="User is veryed Email"
                )

            stmt = (
                select(func.count())
                .select_from(EmailVerifications)
                .join(User, User.id == EmailVerifications.user_id)
                .where(
                    User.id == user.id,
                    EmailVerifications.created_at >= today_start,
                    EmailVerifications.created_at < tomorrow_start,
                )
            )
            count_result = await self.db.execute(stmt)
            verification_count = count_result.scalar_one()
            # return verification_count
            if verification_count > 5:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Bạn đã gửi quá 5 lần trong hôm nay",
                )
            code = self.security.generate_otp()
            self.db.add(
                EmailVerifications(
                    user_id=user.id,
                    code=code,
                    expired_at=datetime.utcnow() + timedelta(minutes=5),
                )
            )
            await self.db.commit()
            await self.db.refresh(user)
            await self.mail_service.send_verification_email(
                email=schema.email, fullname=user.fullname, code=code
            )
            return True

        except Exception:
            await self.db.rollback()
            raise

    async def verify_email_async(self, schema: VerifyEmail, res: Response):
        try:
            user: User | None = await self.db.scalar(
                select(User)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
                .where(User.email == schema.email)
            )
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            if user.is_verified_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Người dùng đã xác thực email",
                )
            email_verify = (
                await self.db.scalars(
                    select(EmailVerifications)
                    .where(EmailVerifications.user_id == user.id)
                    .order_by(desc(EmailVerifications.created_at))
                )
            ).first()
            if not email_verify:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã xác thực không hợp lệ hoặc đã hết hạn.",
                )
            if email_verify.expired_at < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã xác thực không hợp lệ hoặc đã hết hạn.",
                )

            role = await self.db.scalar(select(Role).where(Role.role_name == "USER"))
            if not role:
                role = Role(
                    role_name="USER", details="Customers use the service of the system"
                )
                self.db.add(role)
                await self.db.flush()
            self.db.add(UserRoles(role_id=role.id, user_id=user.id))
            user.is_verified_email = True
            user.is_active = True
            user.email_verified_at = datetime.utcnow()
            user.update_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)
            res.set_cookie(
                key="access_token",
                value=self.security.create_access_token(str(user.id)),
                httponly=True,
                secure=not DEBUG,  # 🟢 Dev = False, Prod = True
                samesite="lax",  # hoặc "none" nếu frontend/backend khác domain
                max_age=60 * 60 * 24,
                path="/",
            )
            roles = [ur.role.role_name for ur in user.user_roles if ur.role]
            return {
                "id": user.id,
                "fullname": user.fullname,
                "email": user.email,
                "avatar": user.avatar,
                "bio": user.bio,
                "facebook_url": user.facebook_url,
                "is_verified_email": bool(user.is_verified_email),
                "email_verified_at": (
                    user.email_verified_at if user.is_verified_email else None
                ),
                "roles": roles,
            }
        except Exception:
            await self.db.rollback()
            raise

    async def me_async(self, user: User) -> dict[str, Any]:
        roles = [ur.role.role_name for ur in user.user_roles if ur.role]
        return {
            "id": user.id,
            "fullname": user.fullname,
            "email": user.email,
            "avatar": user.avatar,
            "bio": user.bio,
            "facebook_url": user.facebook_url,
            "is_verified_email": bool(user.is_verified_email),
            "email_verified_at": (
                user.email_verified_at if user.is_verified_email else None
            ),
            "roles": roles,
        }
