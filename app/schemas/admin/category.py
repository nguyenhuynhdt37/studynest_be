import uuid
from typing import Optional

from pydantic import BaseModel


class UpdateCategory(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    order_index: Optional[int] = None


class CreateCategory(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
