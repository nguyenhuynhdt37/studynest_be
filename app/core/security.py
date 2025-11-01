# app/core/security.py
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict

import bcrypt
import jwt

from app.core.settings import settings


class SecurityService:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = float(settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 🔐 JWT
    def create_access_token(self, sub: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload: Dict[str, Any] = {"sub": sub, "iat": datetime.utcnow(), "exp": expire}
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return str(token)

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    # 🔑 PASSWORD
    @staticmethod
    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    # 🔢 OTP
    @staticmethod
    def generate_otp() -> str:
        return str(secrets.randbelow(10**6)).zfill(6)
        return str(secrets.randbelow(10**6)).zfill(6)
