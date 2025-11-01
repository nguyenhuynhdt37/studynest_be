import uuid

from pydantic import BaseModel


class CreateLesson(BaseModel):
    section_id: uuid.UUID
    title: str
    description: str
    is_preview: bool
    lesson_type: str


class CreateLessonVideo(BaseModel):
    lesson_id: uuid.UUID
