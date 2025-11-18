import decimal
from typing import Optional

from pydantic import BaseModel, Field


class UpdateSettingsSchema(BaseModel):
    platform_fee: Optional[decimal.Decimal] = Field(None, ge=0, le=1)
    hold_days: Optional[int] = Field(None, ge=0, le=365)
    payout_min_balance: Optional[decimal.Decimal] = Field(None, ge=0)
    payout_schedule: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, max_length=10)
    allow_wallet_topup: Optional[bool] = None
    allow_auto_withdraw: Optional[bool] = None
    max_discounts_per_course: Optional[int] = Field(None, ge=0, le=20)
    discount_max_percent: Optional[int] = Field(None, ge=0, le=100)
    discount_min_price: Optional[decimal.Decimal] = Field(None, ge=0)
    course_min_price: Optional[decimal.Decimal] = Field(None, ge=0)
    course_max_price: Optional[decimal.Decimal] = Field(None, ge=0)
    course_default_language: Optional[str] = Field(None, max_length=20)
    embedding_dim: Optional[int] = Field(None, ge=128, le=4096)
    search_top_k: Optional[int] = Field(None, ge=1, le=50)
    rag_max_chunks: Optional[int] = Field(None, ge=1, le=200)
    max_login_attempts: Optional[int] = Field(None, ge=1, le=50)
    lock_time_minutes: Optional[int] = Field(None, ge=1, le=600)
