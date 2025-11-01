import uuid

from pydantic import BaseModel


class LessonActiveSchema(BaseModel):
    type: str
    lesson_id: uuid.UUID