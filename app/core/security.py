import secrets
from datetime import timedelta
from typing import Any, Dict

import bcrypt
import jwt

from app.core.settings import settings
from app.libs.formats.datetime import now_tzinfo


class SecurityService:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = float(settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # ✅ Hỗ trợ async context (dùng được async with)
    async def __aenter__(self):
        # Có thể mở resource async ở đây, ví dụ Redis, httpx.AsyncClient, v.v.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Dọn dẹp tài nguyên async (VD: await client.aclose())
        return False  # Không nuốt exception

    # 🔐 JWT
    async def create_access_token(self, sub: str) -> str:
        expire = now_tzinfo() + timedelta(minutes=self.access_token_expire_minutes)
        payload: Dict[str, Any] = {"sub": sub, "iat": now_tzinfo(), "exp": expire}
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return str(token)

    async def decode_access_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    # 🔑 PASSWORD
    @staticmethod
    async def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    async def verify_password(plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    # 🔢 OTP
    @staticmethod
    async def generate_otp() -> str:
        return str(secrets.randbelow(10**6)).zfill(6)
