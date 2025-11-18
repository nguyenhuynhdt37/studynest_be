import uuid
from typing import Optional

from pydantic import BaseModel, Field


class LessonActiveSchema(BaseModel):
    type: str
    lesson_id: uuid.UUID


class CreateLessonNote(BaseModel):
    time_seconds: int = Field(..., ge=0, description="Thời gian trong video (giây)")
    content: str = Field(..., min_length=1, description="Nội dung ghi chú")


class UpdateLessonNote(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung ghi chú mới")
    time_seconds: Optional[float] = Field(
        None, ge=0, description="Thời gian video (nếu cần cập nhật)"
    )


class CreateLessonComment(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
    parent_id: Optional[uuid.UUID] = Field(
        None, description="ID bình luận cha (nếu là reply)"
    )


class UpdateLessonComment(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
