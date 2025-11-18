import uuid
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService
from app.schemas.lecturer.chapter import (
    CreateCourseSection,
    ReorderSectionsSchema,
    UpdateCourseSection,
)
from app.services.lecturer.chapter import ChapterService

router = APIRouter(prefix="/lecturer/chapters", tags=["Lecturer Chapters"])


@router.get("/{course_id}")
async def createCourseSection(
    course_id: UUID,
    chapter_service: ChapterService = Depends(ChapterService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await chapter_service.get_course_structure(
        course_id=course_id, lecturer_id=lecturer.id
    )


@router.post("/{course_id}/section")
async def create_section(
    course_id: UUID,
    schema: CreateCourseSection = Body(...),
    chapter_service: ChapterService = Depends(ChapterService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await chapter_service.create_section_async(
        course_id=course_id, schema=schema, lecturer_id=lecturer.id
    )


@router.put("/{course_section_id}/edit")
async def update_section(
    course_section_id: UUID,
    schema: UpdateCourseSection = Body(...),
    chapter_service: ChapterService = Depends(ChapterService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await chapter_service.update_section_async(
        course_section_id=course_section_id, schema=schema, lecturer_id=lecturer.id
    )


@router.delete("/{course_section_id}/delete")
async def delete_section(
    course_section_id: uuid.UUID,
    chapter_service: ChapterService = Depends(ChapterService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await chapter_service.delete_section_async(
        course_section_id=course_section_id, lecturer_id=lecturer.id
    )


@router.put("/{course_id}/sections/reorder")
async def reorder_sections(
    course_id: UUID,
    schema: ReorderSectionsSchema = Body(...),
    chapter_service: ChapterService = Depends(ChapterService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await chapter_service.reorder_sections_async(
        course_id=course_id, schema=schema, lecturer_id=lecturer.id
    )
