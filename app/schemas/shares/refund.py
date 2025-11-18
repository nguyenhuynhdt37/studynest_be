import uuid
from typing import Optional

from pydantic import BaseModel, Field


class RefundRequestCreate(BaseModel):
    purchase_item_id: uuid.UUID = Field(
        ..., description="ID purchase_item cần hoàn tiền"
    )
    reason: str = Field(..., max_length=500, description="Lý do hoàn tiền")


class RefundReviewSchema(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    reason: Optional[str] = Field(
        None, description="Lý do từ chối. Bắt buộc khi action = reject."
    )
