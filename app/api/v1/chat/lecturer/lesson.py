from uuid import UUID

from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.db.models.database import User
from app.schemas.chat.lecturer.lesson import (
    CreateDescriptionSchema,
    CreateRewriteTheTitleSchema,
    LessonListSchema,
)
from app.services.chat.lecturer.lessson import LessonService

router = APIRouter(prefix="/lecturers/chat/lesson", tags=["CHAT LECTURER LESSON"])


@router.post("/rewrite_the_title", status_code=201)
async def rewrite_the_title(
    schema: CreateRewriteTheTitleSchema = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LessonService = Depends(LessonService),
):
    await authorization.require_role(["LECTURER"])
    return await service.rewrite_the_title_async(schema)


@router.post("/create_description", status_code=201)
async def create_description(
    schema: CreateDescriptionSchema = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LessonService = Depends(LessonService),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_description_async(schema)


@router.post("/{lesson_id}/video/quizzes", status_code=201)
async def create_quizzes_video(
    lesson_id: UUID,
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LessonService = Depends(LessonService),
):
    lecturer: User = await authorization.require_role(["LECTURER"])
    return await service.create_quizzes_video_async(lesson_id, lecturer.id)


@router.post("/quizzes", status_code=201)
async def create_quizzes_section(
    schema: LessonListSchema = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LessonService = Depends(LessonService),
):
    lecturer: User = await authorization.require_role(["LECTURER"])
    return await service.create_quizzes_from_lessons_async(
        schema.lesson_ids, lecturer.id
    )


@router.post("/code", status_code=201)
async def create_coding_tasks_from_lessons(
    schema: LessonListSchema = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LessonService = Depends(LessonService),
):
    lecturer: User = await authorization.require_role(["LECTURER"])
    return await service.create_coding_tasks_from_lessons_async(
        schema.lesson_ids, lecturer.id
    )
