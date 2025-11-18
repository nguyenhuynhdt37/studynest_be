from uuid import UUID

from pydantic import BaseModel


class CreateRewriteTheTitleSchema(BaseModel):
    title: str


class CreateDescriptionSchema(BaseModel):
    title: str
    section_name: str


class LessonListSchema(BaseModel):
    lesson_ids: list[UUID]
