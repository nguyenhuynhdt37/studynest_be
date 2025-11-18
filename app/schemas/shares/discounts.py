import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DiscountTargetItem(BaseModel):
    course_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None


class DiscountCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None

    discount_code: Optional[str] = None
    is_hidden: Optional[bool] = False

    applies_to: str  # global | course | category | specific
    discount_type: str  # percent | fixed

    percent_value: Optional[float] = None
    fixed_value: Optional[float] = None

    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None

    start_at: datetime
    end_at: datetime
    auto_targets_weak_courses: bool = False
    targets: Optional[List[DiscountTargetItem]] = None


##########


class DiscountAvailableRequest(BaseModel):
    course_ids: List[uuid.UUID]


class ApplyDiscountRequest(BaseModel):
    course_ids: List[uuid.UUID]
    discount_input: str  # discount code or discount id


class DiscountTargetEditSchema(BaseModel):
    course_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None


class DiscountEditSchema(BaseModel):
    name: str = Field(..., description="Tên mã giảm giá")
    description: Optional[str] = Field(None, description="Mô tả")
    discount_code: str = Field(..., description="Mã code (nếu chưa dùng có thể đổi)")
    is_hidden: bool = False

    applies_to: str = Field(..., description="course | category | global | specific")
    discount_type: str = Field(..., description="percent | fixed")

    percent_value: Optional[int] = None
    fixed_value: Optional[int] = None

    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None

    start_at: datetime
    end_at: datetime
    auto_targets_weak_courses: bool = False
    targets: Optional[List[DiscountTargetEditSchema]] = None
