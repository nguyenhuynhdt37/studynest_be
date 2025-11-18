# app/schemas/purchase/purchase_checkout.py

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class PurchaseCheckoutSchema(BaseModel):
    course_ids: List[uuid.UUID] = Field(..., description="Danh sách khóa học muốn mua")
    discount_code: Optional[str] = Field(None, description="Mã giảm giá (nếu có)")
