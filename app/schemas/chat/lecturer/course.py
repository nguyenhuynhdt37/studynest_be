from pydantic import BaseModel


class CreateShortCourseDescriptionSchema(BaseModel):
    course_name: str


class CreateCourseDescriptionSchema(BaseModel):
    course_name: str
    short_description: str
    category_name: str
    topic_name: str | None = None


class CreateCourseObjectivesAndAudienceSchema(BaseModel):
    course_name: str
    short_description: str
    category_name: str
    topic_name: str | None = None
