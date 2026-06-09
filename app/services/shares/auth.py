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
from app.core.ws_manager import ws_manager
from app.db.models.database import EmailVerifications, Role, User, UserRoles, Sessions
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import strip_tz
from app.schemas.auth.user import (
    GoogleLogin,
    LoginUser,
    RefreshEmail,
    SendOtp,
    UserCreate,
    VerifyEmail,
    VerifyOtp,
)
from app.schemas.shares.notification import NotificationCreateSchema
from app.services.shares.mailer import MailerService
from app.services.shares.notification import NotificationService
from app.services.shares.wallets import WalletsService


class AuthService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        security: SecurityService = Depends(SecurityService),
        mail_service: MailerService = Depends(MailerService),
        wallet_service: WalletsService = Depends(WalletsService),
    ):
        self.db = db
        self.security = security
        self.mail_service = mail_service
        self.wallet_service = wallet_service

    async def _create_session(self, user_id: Any, res: Response, user_agent: str | None = None, ip: str | None = None):
        # 1. Tạo session_id và refresh_token
        refresh_token = await self.security.generate_refresh_token()
        refresh_token_hash = await self.security.hash_token(refresh_token)

        # 2. Lưu vào DB (Sessions)
        new_session = Sessions(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip,
            expired_at=get_now() + timedelta(days=30) # Refresh token sống 30 ngày
        )
        self.db.add(new_session)
        await self.db.flush() # Để lấy new_session.id gán vào JWT

        # 3. Tạo Access Token (chứa sid)
        access_token = await self.security.create_access_token(sub=str(user_id), sid=str(new_session.id))

        # 4. Set Cookies
        # Access Token
        res.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # Dev = False, Prod = True
            samesite="lax",
            max_age=60 * 15, # 15 phút (nên ngắn hạn)
            path="/",
        )
        # Refresh Token (Cái này mới quan trọng)
        res.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24 * 30, # 30 ngày
            path="/",
        )
        return {
            "message": "Login successful",
            "session_id": str(new_session.id),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expired_at": new_session.expired_at
        }

    async def _broadcast_new_session(
        self,
        user_id: Any,
        session_id: str,
        user_agent: str | None = None,
        ip: str | None = None,
        login_method: str = "password",
        explicit_device_type: str | None = None,
    ) -> None:
        try:
            active_other_session = await self.db.scalar(
                select(Sessions.id).where(
                    Sessions.user_id == user_id,
                    Sessions.id != session_id,
                    Sessions.is_revoked.is_(False),
                    Sessions.expired_at >= get_now(),
                )
            )
            if not active_other_session:
                return

            device_type = self._detect_device_type(user_agent, explicit_type=explicit_device_type)
            session_payload = {
                "id": session_id,
                "device_type": device_type,
                "ip_address": ip,
                "user_agent": user_agent,
                "login_method": login_method,
                "created_at": get_now().isoformat(),
            }

            notification = await NotificationService(self.db).create_notification_async(
                NotificationCreateSchema(
                    user_id=user_id,
                    title="Phát hiện đăng nhập mới",
                    content=(
                        f"Có đăng nhập mới bằng {login_method} trên {device_type}. "
                        f"IP: {ip or 'không rõ'}."
                    ),
                    type="security",
                    role_target=["USER"],
                    action="review_session",
                    metadata={
                        "event": "auth.new_session",
                        "session": session_payload,
                    },
                )
            )

            await ws_manager.broadcast(
                f"AUTH_{user_id}",
                {
                    "type": "auth.new_session",
                    "data": {
                        "notification_id": str(notification.id),
                        "session": session_payload,
                    },
                },
            )
        except Exception:
            pass

    def _detect_device_type(self, user_agent: str | None, explicit_type: str | None = None) -> str:
        if explicit_type and explicit_type.upper() in ["IOS", "ANDROID", "WEB"]:
            return explicit_type.upper()
            
        ua_lower = (user_agent or "").lower()
        
        # iOS Keywords
        if any(k in ua_lower for k in ["iphone", "ipad", "ipod", "ios", "cfnetwork", "darwin"]):
            return "IOS"
            
        # Android Keywords
        if any(k in ua_lower for k in ["android", "okhttp", "dalvik"]):
            return "ANDROID"
            
        # General Mobile keyword
        if "mobile" in ua_lower:
            return "ANDROID"
            
        return "WEB"

    async def login_async(self, schema: LoginUser, res: Response, user_agent: str | None = None, ip: str | None = None):
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
                    },
                )
            if not await self.security.verify_password(
                schema.password, user.password or ""
            ):
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "INVALID_CREDENTIALS",
                        "message": "Email hoặc mật khẩu không đúng",
                    },
                )

            # 2️⃣ TÀI KHOẢN ĐÃ BỊ XÓA, EMAIL CHƯA VERIFY, BANNED... (giữ nguyên)
            if user.deleted_at:
                raise HTTPException(
                    status_code=403,
                    detail={"error_code": "ACCOUNT_DELETED", "message": "Tài khoản đã bị xóa"},
                )
            if not user.is_verified_email:
                raise HTTPException(
                    status_code=403,
                    detail={"error_code": "EMAIL_NOT_VERIFIED", "message": "Vui lòng xác thực email"},
                )
            if user.is_banned:
                raise HTTPException(
                    status_code=403,
                    detail={"error_code": "ACCOUNT_BANNED", "message": "Tài khoản bị khóa"},
                )

            # 5️⃣ TẠO PHIÊN (SESSION) MỚI
            login_result = await self._create_session(user.id, res, user_agent, ip)
            
            # Cập nhật last_login_at
            user.last_login_at = get_now()
            await self.db.commit()
            await self._broadcast_new_session(
                user.id,
                login_result["session_id"],
                user_agent,
                ip,
                login_method="password",
                explicit_device_type=schema.device_type,
            )
            
            return login_result
        except Exception:
            await self.db.rollback()
            raise

    async def check_email_async(self, email: str) -> dict[str, Any]:
        existing_id = (
            await self.db.scalars(select(User.id).where(User.email == email))
        ).first()
        if existing_id:
            return {"available": False, "message": "Email đã được sử dụng"}
        return {"available": True, "message": "Email khả dụng"}

    async def register_async(self, schema: UserCreate) -> dict[str, Any]:
        try:
            existing_id = (
                await self.db.scalars(select(User.id).where(User.email == schema.email))
            ).first()
            if existing_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "EMAIL_TAKEN", "message": "Email đã được sử dụng"},
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
            await self.mail_service.send_verification_email(
                schema.email, schema.full_name or "", code
            )
            await self.db.commit()
            return {"message": "send Email ok"}
        except Exception:
            await self.db.rollback()
            raise

    async def logout_async(self, res: Response, sid: str | None = None):
        try:
            if sid:
                # Vô hiệu hóa session trong DB
                stmt = select(Sessions).where(Sessions.id == sid)
                session = (await self.db.execute(stmt)).scalar_one_or_none()
                if session:
                    session.is_revoked = True
                    await self.db.commit()

            # Xóa cookies
            res.delete_cookie(key="access_token", path="/")
            res.delete_cookie(key="refresh_token", path="/")
            return "Logout done"
        except Exception:
            await self.db.rollback()
            raise

    async def refesh_email_async(self, schema: RefreshEmail):
        try:
            today_start = get_now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_start = today_start + timedelta(days=1)
            user = (
                await self.db.scalars(select(User).where((User.email == schema.email)))
            ).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "USER_NOT_FOUND", "message": "Không tìm thấy người dùng"}
                )
            if user.is_verified_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail={"error_code": "EMAIL_ALREADY_VERIFIED", "message": "Email đã được xác thực"}
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
                    status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "USER_NOT_FOUND", "message": "Không tìm thấy người dùng"}
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
            
            # Cập nhật last_login_at vì user sẽ được login ngay sau khi verify
            user.last_login_at = get_now()
            
            # Tạo session mới
            login_result = await self._create_session(user.id, res)
            
            # Tự động tạo ví cho người dùng mới xác thực
            await self.wallet_service.get_or_create_wallet_async(user.id)
            
            await self.db.commit()
            await self.db.refresh(user)
            await self._broadcast_new_session(
                user.id,
                login_result["session_id"],
                login_method="email_verify",
            )
            
            roles = [ur.role.role_name for ur in user.user_roles if ur.role]
            return {
                **login_result,
                "user": {
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
            }
        except Exception:
            await self.db.rollback()
            raise

    async def me_async(self, user: User) -> dict[str, Any]:
        # Tự động tạo ví nếu chưa có (Self-healing)
        await self.wallet_service.get_or_create_wallet_async(user.id)
        await self.db.commit()

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
            # ====== Preferences ======
            "preferences_str": user.preferences_str,
            # ====== Learning Goals ======
            "learning_goals": user.learning_goals,
            "daily_goal_minutes": user.daily_goal_minutes,
            "preferred_learning_style": user.preferred_learning_style,
            # ====== PayPal (chuẩn hóa để dùng rút tiền) ======
            "paypal_email": user.paypal_email,
            "paypal_payer_id": paypal_payer_id,
            "paypal_raw_payer_id": user.paypal_payer_id,  # để debug nếu cần
            # ====== System timestamps ======
            "created_at": user.create_at,
            "updated_at": user.update_at,
        }

    async def login_google_async(self, schema: GoogleLogin, res: Response, user_agent: str | None = None, ip: str | None = None):
        try:
            print(f"DEBUG: Using Client ID: {settings.GOOGLE_API_CLIENT_ID_LOGIN_GOOGLE}")
            info = id_token.verify_oauth2_token(
                schema.credential,
                requests.Request(),
                settings.GOOGLE_API_CLIENT_ID_LOGIN_GOOGLE,
            )

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

            # 3) TỰ TẠO USER MỚI (khi chưa có)
            if not user:
                user = User(
                    email=email,
                    fullname=fullname or "",
                    avatar=avatar,
                    password="google-oauth",
                    is_verified_email=True,
                    email_verified_at=get_now(),
                    is_active=True,
                    create_at=get_now(),
                    update_at=get_now(),
                )
                self.db.add(user)
                await self.db.flush()

                role = await self.db.scalar(select(Role).where(Role.role_name == "USER"))
                if not role:
                    role = Role(role_name="USER", details="Default customer role")
                    self.db.add(role)
                    await self.db.flush()
                self.db.add(UserRoles(user_id=user.id, role_id=role.id))
                await self.db.commit()
                await self.db.refresh(user)

            # 4) CHECK BANNED / DELETED
            if user.deleted_at or user.is_banned:
                raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa hoặc xóa")

            # 6) TẠO PHIÊN (SESSION) MỚI
            login_result = await self._create_session(user.id, res, user_agent, ip)
            
            # Cập nhật last_login_at
            user.last_login_at = get_now()
            await self.db.commit()
            await self._broadcast_new_session(
                user.id,
                login_result["session_id"],
                user_agent,
                ip,
                login_method="google",
                explicit_device_type=schema.device_type,
            )
            
            return login_result

        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print("Google login error detail:", str(e))
            traceback.print_exc()
            await self.db.rollback()
            raise HTTPException(400, f"Token Google không hợp lệ: {str(e)}")

    async def refresh_token_async(self, refresh_token: str | None, res: Response, user_agent: str | None = None, ip: str | None = None):
        if not refresh_token:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_REFRESH_TOKEN", "message": "Thiếu mã làm mới phiên"})

        # 1. Hash token khách gửi lên để tìm trong DB
        token_hash = await self.security.hash_token(refresh_token)

        # 2. Tìm session tương ứng
        stmt = select(Sessions).where(Sessions.refresh_token_hash == token_hash)
        session = (await self.db.execute(stmt)).scalar_one_or_none()

        if not session or session.is_revoked or strip_tz(session.expired_at) < get_now():
            # Nếu token không hợp lệ/bị hack -> Xóa sạch dấu vết
            res.delete_cookie("access_token")
            res.delete_cookie("refresh_token")
            raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn")

        # 3. REFRESH TOKEN ROTATION: Xóa session cũ, tạo session mới hoàn toàn
        user_id = session.user_id
        await self.db.delete(session)
        await self.db.flush()

        # 4. Cấp cặp token mới
        return await self._create_session(user_id, res, user_agent, ip)

    def _serialize_session(self, session: Sessions, current_sid: str | None = None) -> dict[str, Any]:
        user_agent = session.user_agent or ""

        return {
            "id": str(session.id),
            "device_type": self._detect_device_type(user_agent),
            "device_name": session.device_name,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "last_used_at": session.updated_at,
            "created_at": session.created_at,
            "expired_at": session.expired_at,
            "is_current": str(session.id) == str(current_sid) if current_sid else False,
        }

    async def list_sessions_async(self, user_id: Any, current_sid: str | None = None):
        stmt = (
            select(Sessions)
            .where(
                Sessions.user_id == user_id,
                Sessions.is_revoked.is_(False),
                Sessions.expired_at >= get_now(),
            )
            .order_by(desc(Sessions.created_at))
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        return {
            "sessions": [self._serialize_session(session, current_sid) for session in sessions],
            "total": len(sessions)
        }

    async def logout_all_async(self, user_id: Any, keep_sid: str | None = None):
        # Thu hồi tất cả các session của user
        stmt = select(Sessions).where(Sessions.user_id == user_id, Sessions.is_revoked.is_(False))
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        revoked_count = 0
        revoked_session_ids: list[str] = []
        
        for session in sessions:
            if keep_sid and str(session.id) == str(keep_sid):
                continue
            session.is_revoked = True
            revoked_count += 1
            revoked_session_ids.append(str(session.id))
            
        await self.db.commit()
        return {
            "message": "Đã đăng xuất khỏi các thiết bị",
            "revoked_count": revoked_count,
            "revoked_session_ids": revoked_session_ids,
        }

    async def revoke_session_async(self, session_id: str, user_id: Any):
        import uuid
        try:
            if isinstance(session_id, str):
                session_id = uuid.UUID(session_id)
        except Exception:
            raise HTTPException(400, "Invalid session ID format")

        stmt = select(Sessions).where(Sessions.id == session_id, Sessions.user_id == user_id)
        session = (await self.db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên đăng nhập")

        session.is_revoked = True
        await self.db.commit()
        return {"message": "Đã đăng xuất thiết bị thành công", "revoked_session_id": str(session.id)}

    async def send_otp_async(self, schema: SendOtp):
        try:
            # 1. Tìm user theo email
            stmt = select(User).where(User.email == schema.email)
            user = (await self.db.execute(stmt)).scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_code": "USER_NOT_FOUND",
                        "message": "Không tìm thấy người dùng với email này",
                    },
                )

            if user.is_banned:
                raise HTTPException(
                    status_code=403,
                    detail={"error_code": "ACCOUNT_BANNED", "message": "Tài khoản đã bị khóa"},
                )

            # 2. Tạo mã OTP
            code = await self.security.generate_otp()
            expired_at = get_now() + timedelta(minutes=10)

            # 3. Lưu OTP vào DB
            verification = EmailVerifications(
                user_id=user.id,
                code=code,
                expired_at=expired_at
            )
            self.db.add(verification)
            await self.db.commit()

            # 4. Gửi email
            await self.mail_service.send_login_otp_email(
                email=user.email,
                fullname=user.fullname,
                code=code
            )

            return {
                "message": "Mã OTP đã được gửi đến email của bạn",
                "resend_available_in": 60,
                "otp_expires_in": 600
            }
        except HTTPException:
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def verify_otp_login_async(self, schema: VerifyOtp, res: Response, user_agent: str | None = None, ip: str | None = None):
        try:
            identifier = schema.email or schema.phone
            if not identifier:
                raise HTTPException(400, "Email hoặc số điện thoại là bắt buộc")

            # 1. Tìm user
            stmt = select(User).where(User.email == identifier)
            user = (await self.db.execute(stmt)).scalar_one_or_none()

            if not user:
                raise HTTPException(404, "Không tìm thấy người dùng")

            # 2. Kiểm tra OTP gần nhất
            stmt = (
                select(EmailVerifications)
                .where(EmailVerifications.user_id == user.id)
                .order_by(desc(EmailVerifications.created_at))
                .limit(1)
            )
            verification = (await self.db.execute(stmt)).scalar_one_or_none()

            if not verification or verification.code != schema.otp_code:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "INVALID_OTP",
                        "message": "Mã OTP không đúng hoặc đã hết hạn",
                    },
                )

            if verification.expired_at < get_now():
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "OTP_EXPIRED",
                        "message": "Mã OTP đã hết hạn",
                    },
                )

            # 3. Tạo session mới
            login_result = await self._create_session(user.id, res, user_agent, ip)

            # Cập nhật thông tin đăng nhập
            user.last_login_at = get_now()
            if not user.is_verified_email:
                user.is_verified_email = True
                user.email_verified_at = get_now()
            
            await self.db.commit()
            await self._broadcast_new_session(
                user.id,
                login_result["session_id"],
                user_agent,
                ip,
                login_method="otp",
                explicit_device_type=schema.device_type,
            )

            return login_result
        except HTTPException:
            raise
        except Exception:
            await self.db.rollback()
            raise
