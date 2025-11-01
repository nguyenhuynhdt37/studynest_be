from uuid import UUID

from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService
from app.schemas.lecturer.chapter import CreateCourseSection
from app.services.lecturer.chapter import ChapterService

router = APIRouter(prefix="/lecturer/chapters", tags=["Lecturer Chapters"])


def get_chapter_service(
    chapter_service: ChapterService = Depends(ChapterService),
) -> ChapterService:
    return chapter_service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.get("/{course_id}")
async def createCourseSection(
    course_id: UUID,
    chapter_service: ChapterService = Depends(get_chapter_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await chapter_service.get_course_structure(
        course_id=course_id, lecturer_id=lecturer.id
    )


@router.post("/{course_id}/section")
async def create_section(
    course_id: UUID,
    schema: CreateCourseSection = Body(...),
    chapter_service: ChapterService = Depends(get_chapter_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await chapter_service.create_section_async(
        course_id=course_id, schema=schema, lecturer_id=lecturer.id
    )
