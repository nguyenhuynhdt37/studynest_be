import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, UploadFile, status

from app.core.deps import AuthorizationService
from app.schemas.lecturer.lesson import CreateLesson
from app.services.lecturer.lesson import LessonService

router = APIRouter(prefix="/lecturer/lessons", tags=["User Lessons"])


def get_lesson_service(
    lesson_service: LessonService = Depends(LessonService),
) -> LessonService:
    return lesson_service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.post("/create", status_code=status.HTTP_200_OK)
async def createLesson(
    lesson_service: LessonService = Depends(get_lesson_service),
    schema: CreateLesson = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await lesson_service.create_lesson_async(schema, lecturer)


@router.post("/create/video/{lesson_id}", status_code=status.HTTP_200_OK)
async def createLessonVideo(
    lesson_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    lesson_service: LessonService = Depends(get_lesson_service),
    video: UploadFile = File(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
) -> dict[str, str]:
    lecturer = await authorization.require_role(["LECTURER"])
    return await lesson_service.upload_video_async(
        video, lecturer, lesson_id, background_tasks
    )
