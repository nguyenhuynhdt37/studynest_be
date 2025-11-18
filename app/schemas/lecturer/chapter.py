from uuid import UUID

from pydantic import BaseModel


class CreateCourseSection(BaseModel):
    title: str


class UpdateCourseSection(BaseModel):
    title: str | None = None


class ReorderSectionsSchema(BaseModel):
    section_ids: list[UUID]
