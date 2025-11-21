from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService
from app.schemas.lecturer.chapter import CreateCourseSection
from app.services.lecturer.course_sections import CourseSectionService

router = APIRouter(
    prefix="/lecturer/course_sections", tags=["Lecturer Course_sections"]
)


def get_course_section_service(
    course_section_service: CourseSectionService = Depends(CourseSectionService),
) -> CourseSectionService:
    return course_section_service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.post("/create")
async def createCourseSection(
    schema: CreateCourseSection = Body(...),
    course_section_service: CourseSectionService = Depends(get_course_section_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_section_service.create_section_async(schema, lecturer)
