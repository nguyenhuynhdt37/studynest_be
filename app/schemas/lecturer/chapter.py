from pydantic import BaseModel


class CreateCourseSection(BaseModel):
    title: str
