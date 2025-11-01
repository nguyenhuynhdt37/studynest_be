import uuid
from http.client import HTTPException

import httpx
from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthorizationService
from app.core.settings import settings
from app.db.models.database import User
from app.db.sesson import get_session
from app.services.user.learning import LearningService

router = APIRouter(prefix="/learning", tags=["User Learning"])


def get_learning_service(
    service: LearningService = Depends(LearningService),
) -> LearningService:
    return service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.get("/{course_slug}")
async def get_course_enrolled(
    course_slug: str,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_course_enrolled_async(course_slug, user)


@router.get("/{course_id}/instructor")
async def get_instructor_by_course_id(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_instructor_by_course_id_async(course_id, user)


@router.get("/{course_id}/curriculum")
async def get_course_curriculum(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_course_curriculum_async(course_id, user)


@router.get("/{course_id}/view/active")
async def get_lesson_active(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    lesson_type, lesson_id = (
        await learning_service.get_type_and_lesson_id_by_course_id_active(
            course_id, user
        )
    )
    match lesson_type:
        case "video":
            return await learning_service.get_lesson_video_async(lesson_id, user)
        case _:
            raise


@router.post("/{course_id}/active/{lesson_id}")
async def set_active_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.set_active_lesson_async(course_id, lesson_id, user)


@router.get("/{lesson_id}/check_prev_next")
async def get_prev_next_lesson(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_prev_next_lesson_async(lesson_id, user)


@router.post("/{lesson_id}/next")
async def get_next_lesson_in_course(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_next_lesson_in_course_async(lesson_id, user, True)


@router.post("/{lesson_id}/prev")
async def get_prev_lesson_in_course(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.get_previous_lesson_in_course_async(lesson_id, user)


@router.post("/{lesson_id}/complete")
async def mark_lesson_completed(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(get_learning_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await learning_service.mark_lesson_completed_async(lesson_id, user)
