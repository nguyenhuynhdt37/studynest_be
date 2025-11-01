import uuid
from typing import List, Literal

from pydantic import BaseModel, Field

Level = Literal["all", "beginner", "intermediate", "advanced"]
Language = Literal["vi", "en"]  # mở rộng nếu cần
Currency = Literal["VND", "USD"]  # mở rộng nếu cần


class CreateCourse(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category_id: uuid.UUID
    topic_id: uuid.UUID | None = None

    subtitle: str | None = None
    description: str | None = None
    is_lock_lesson: bool = False
    level: Level = "all"  # tránh trượt CHECK; default khớp DB
    language: Language = "vi"  # khớp default DB

    is_published: bool = False
    outcomes: List[str] | None = None
    requirements: List[str] | None = None
    target_audience: List[str] | None = None

    base_price: float = 0.0  # >= 0
    currency: Currency = "VND"


class UpdateCourse(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category_id: uuid.UUID
    topic_id: uuid.UUID | None = None

    subtitle: str | None = None
    description: str | None = None
    is_lock_lesson: bool = False
    level: Level = "all"  # tránh trượt CHECK; default khớp DB
    language: Language = "vi"  # khớp default DB

    is_published: bool = False
    outcomes: List[str] | None = None
    requirements: List[str] | None = None
    target_audience: List[str] | None = None

    base_price: float = 0.0  # >= 0
    currency: Currency = "VND"


class CourseReview(BaseModel):
    content: str
    rating: float
