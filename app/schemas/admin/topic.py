from uuid import UUID

from pydantic import BaseModel, Field


class TopicBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    order_index: int | None = 1
    is_active: bool = True
    category_id: UUID


class TopicCreate(BaseModel):
    category_id: UUID = Field(..., description="ID của category cha")
    name: str
    description: str | None = None
    is_active: bool = True


class TopicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    category_id: UUID | None = None
