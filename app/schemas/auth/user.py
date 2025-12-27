import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=6, max_length=72)]
    full_name: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool

    class Config:
        from_attributes = True


class LoginUser(BaseModel):
    email: EmailStr
    password: str


class RefreshEmail(BaseModel):
    email: EmailStr


class VerifyEmail(BaseModel):
    email: EmailStr
    code: str


class RoleOut(BaseModel):
    id: uuid.UUID
    role_name: str

    class Config:
        orm_mode = True


class EditUser(BaseModel):
    email: str
    fullname: str | None


class BlockUser(BaseModel):
    is_block_permanently: bool = False
    banned_reason: str
    banned_until: datetime | None


class GoogleLogin(BaseModel):
    credential: str
