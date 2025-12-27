from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import Depends, HTTPException, Response, status
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc

from app.core.security import SecurityService
from app.core.settings import settings
from app.db.models.database import EmailVerifications, Role, User, UserRoles
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.schemas.auth.user import (
    GoogleLogin,
    LoginUser,
    RefreshEmail,
    UserCreate,
    VerifyEmail,
)
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
            
            # 1️⃣ KHÔNG TÌM THẤY USER HOẶC SAI MẬT KHẨU
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "INVALID_CREDENTIALS",
                        "message": "Email hoặc mật khẩu không đúng",
                    }
                )
            if not await self.security.verify_password(
                schema.password, user.password or ""
            ):
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "INVALID_CREDENTIALS",
                        "message": "Email hoặc mật khẩu không đúng",
                    }
                )

            # 2️⃣ TÀI KHOẢN ĐÃ BỊ XÓA
            if user.deleted_at:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error_code": "ACCOUNT_DELETED",
                        "message": "Tài khoản đã bị xóa khỏi hệ thống",
                        "deleted_at": str(user.deleted_at),
                        "reason": user.deleted_until or "Không có lý do cụ thể",
                    }
                )

            # 3️⃣ CHƯA XÁC THỰC EMAIL
            if not user.is_verified_email:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error_code": "EMAIL_NOT_VERIFIED",
                        "message": "Vui lòng xác thực email trước khi đăng nhập",
                        "email": user.email,
                    }
                )

            # 4️⃣ TÀI KHOẢN BỊ KHÓA (BANNED)
            if user.is_banned:
                # Kiểm tra nếu đã hết hạn ban → tự động mở khóa
                if user.banned_until and user.banned_until < get_now():
                    user.is_banned = False
                    user.banned_reason = None
                    user.banned_until = None
                    await self.db.commit()
                else:
                    # Xác định loại ban
                    is_permanent = user.banned_until is None
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error_code": "ACCOUNT_BANNED_PERMANENT" if is_permanent else "ACCOUNT_BANNED_TEMPORARY",
                            "message": "Tài khoản đã bị khóa vĩnh viễn" if is_permanent else "Tài khoản đang bị tạm khóa",
                            "reason": user.banned_reason or "Không có lý do cụ thể",
                            "banned_until": str(user.banned_until) if user.banned_until else None,
                            "is_permanent": is_permanent,
                        }
                    )

            # 5️⃣ TẠO TOKEN VÀ SET COOKIE
            res.set_cookie(
                key="access_token",
                value=await self.security.create_access_token(str(user.id)),
                httponly=True,
                secure=False,  # Dev = False, Prod = True
                samesite="lax",  # FE và BE phải cùng domain (cùng localhost hoặc cùng 127.0.0.1)
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
            password_hash = await self.security.hash_password(schema.password)
            new_user.is_active = False
            new_user.password = password_hash
            new_user.create_at = get_now()
            self.db.add(new_user)
            await self.db.flush()

            # ✅ GÁN ROLE USER MẶC ĐỊNH NGAY KHI TẠO TÀI KHOẢN
            role = await self.db.scalar(select(Role).where(Role.role_name == "USER"))
            if not role:
                role = Role(
                    role_name="USER",
                    details="Customers use the service of the system",
                )
                self.db.add(role)
                await self.db.flush()
            self.db.add(UserRoles(user_id=new_user.id, role_id=role.id))

            code = await self.security.generate_otp()
            expired_at = get_now() + timedelta(minutes=5)
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
            secure=False,  # 🟢 Dev = False
            samesite="lax",
            path="/",
            domain=None,
        )
        return "Logout done"

    async def refesh_email_async(self, schema: RefreshEmail):
        try:
            today_start = get_now().replace(hour=0, minute=0, second=0, microsecond=0)
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
            code = await self.security.generate_otp()
            self.db.add(
                EmailVerifications(
                    user_id=user.id,
                    code=code,
                    expired_at=get_now() + timedelta(minutes=5),
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
            if email_verify.expired_at < get_now():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mã xác thực không hợp lệ hoặc đã hết hạn.",
                )

            # User đã được gán role USER từ lúc register, chỉ cần cập nhật trạng thái
            user.is_verified_email = True
            user.is_active = True
            user.email_verified_at = get_now()
            user.update_at = get_now()
            await self.db.commit()
            await self.db.refresh(user)
            res.set_cookie(
                key="access_token",
                value=await self.security.create_access_token(str(user.id)),
                httponly=True,
                secure=False,  # Dev = False, Prod = True
                samesite="lax",  # FE và BE phải cùng domain (cùng localhost hoặc cùng 127.0.0.1)
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

        # Chuẩn hóa PayPal payer_id (nếu dạng URL)
        raw_payer_id = user.paypal_payer_id
        paypal_payer_id = raw_payer_id.split("/")[-1] if raw_payer_id else None

        return {
            "id": user.id,
            "fullname": user.fullname,
            "email": user.email,
            "avatar": user.avatar,
            "bio": user.bio,
            "facebook_url": user.facebook_url,
            # ====== Info cơ bản ======
            "birthday": user.birthday,
            "conscious": user.conscious,
            "district": user.district,
            "citizenship_identity": user.citizenship_identity,
            # ====== Account status ======
            "is_verified_email": bool(user.is_verified_email),
            "email_verified_at": (
                user.email_verified_at if user.is_verified_email else None
            ),
            "is_banned": bool(user.is_banned),
            "banned_reason": user.banned_reason,
            "banned_until": user.banned_until,
            "last_login_at": user.last_login_at,
            # ====== Auth ======
            "roles": roles,
            # ====== PayPal (chuẩn hóa để dùng rút tiền) ======
            "paypal_email": user.paypal_email,
            "paypal_payer_id": paypal_payer_id,
            "paypal_raw_payer_id": user.paypal_payer_id,  # để debug nếu cần
            # ====== System timestamps ======
            "created_at": user.create_at,
            "updated_at": user.update_at,
        }

    async def login_google_async(self, schema: GoogleLogin, res: Response):
        try:
            # 1) VERIFY GOOGLE ID TOKEN
            info = id_token.verify_oauth2_token(
                schema.credential,
                requests.Request(),
                settings.GOOGLE_API_CLIENT_ID_LOGIN_GOOGLE,
            )

            google_uid = info.get("sub")
            email = info.get("email")
            fullname = info.get("name")
            avatar = info.get("picture")

            if not email:
                raise HTTPException(400, "Google không trả về email hợp lệ")

            # 2) TÌM USER TRONG DB
            stmt = (
                select(User)
                .where(User.email == email)
                .options(selectinload(User.user_roles).selectinload(UserRoles.role))
            )
            user = (await self.db.execute(stmt)).scalar_one_or_none()

            # ─────────────────────────────────────────────
            # 3) TỰ TẠO USER MỚI (khi chưa có)
            # ─────────────────────────────────────────────
            if not user:
                user = User(
                    email=email,
                    fullname=fullname or "",
                    avatar=avatar,
                    password="google-oauth",  # không dùng mật khẩu
                    is_verified_email=True,  # Google đảm bảo email verified
                    email_verified_at=get_now(),
                    is_active=True,
                    create_at=get_now(),
                    update_at=get_now(),
                )

                self.db.add(user)
                await self.db.flush()

                # tìm role USER
                role = await self.db.scalar(
                    select(Role).where(Role.role_name == "USER")
                )
                if not role:
                    role = Role(
                        role_name="USER",
                        details="Customers use the service of the system",
                    )
                    self.db.add(role)
                    await self.db.flush()

                # add vai trò cho user mới
                self.db.add(UserRoles(user_id=user.id, role_id=role.id))

                await self.db.commit()
                await self.db.refresh(user)

            # ─────────────────────────────────────────────
            # 4) CHECK TÀI KHOẢN ĐÃ BỊ XÓA
            # ─────────────────────────────────────────────
            if user.deleted_at:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error_code": "ACCOUNT_DELETED",
                        "message": "Tài khoản đã bị xóa khỏi hệ thống",
                        "deleted_at": str(user.deleted_at),
                        "reason": user.deleted_until or "Không có lý do cụ thể",
                    }
                )

            # ─────────────────────────────────────────────
            # 5) CHECK BANNED ACCOUNT
            # ─────────────────────────────────────────────
            if user.is_banned:
                if user.banned_until and user.banned_until < get_now():
                    # hết hạn ban → mở lại
                    user.is_banned = False
                    user.banned_reason = None
                    user.banned_until = None
                    await self.db.commit()
                else:
                    is_permanent = user.banned_until is None
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error_code": "ACCOUNT_BANNED_PERMANENT" if is_permanent else "ACCOUNT_BANNED_TEMPORARY",
                            "message": "Tài khoản đã bị khóa vĩnh viễn" if is_permanent else "Tài khoản đang bị tạm khóa",
                            "reason": user.banned_reason or "Không có lý do cụ thể",
                            "banned_until": str(user.banned_until) if user.banned_until else None,
                            "is_permanent": is_permanent,
                        }
                    )

            # ─────────────────────────────────────────────
            # 6) TẠO TOKEN + SET COOKIE
            # ─────────────────────────────────────────────
            token = await self.security.create_access_token(str(user.id))

            res.set_cookie(
                key="access_token",
                value=token,
                httponly=True,
                secure=False,  # Dev = False, Prod = True
                samesite="lax",  # FE và BE phải cùng domain (cùng localhost hoặc cùng 127.0.0.1)
                max_age=60 * 60 * 24,
                path="/",
            )

            return {"message": "Login Google successful"}

        except HTTPException:
            raise
        except Exception as e:
            print("Google login error:", e)
            await self.db.rollback()
            raise HTTPException(400, "Token Google không hợp lệ")
