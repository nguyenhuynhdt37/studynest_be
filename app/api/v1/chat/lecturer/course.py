from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.chat.lecturer.course import (
    CreateCourseDescriptionSchema,
    CreateCourseObjectivesAndAudienceSchema,
    CreateShortCourseDescriptionSchema,
)
from app.services.chat.lecturer.course import CourseService

router = APIRouter(prefix="/admin/chat/course", tags=["CHAT ADMIN COURSE"])


def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


def get_course_service(
    course_service: CourseService = Depends(CourseService),
) -> CourseService:
    return course_service


@router.post("/create/short_description", status_code=201)
async def create_short_description(
    schema: CreateShortCourseDescriptionSchema = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: CourseService = Depends(get_course_service),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_short_description_async(schema)


@router.post("/create/description", status_code=201)
async def create_description(
    schema: CreateCourseDescriptionSchema = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: CourseService = Depends(get_course_service),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_description_async(schema)


@router.post("/create/learning_goals", status_code=201)
async def create_learning_goals(
    schema: CreateCourseObjectivesAndAudienceSchema = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: CourseService = Depends(get_course_service),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_learning_goals_async(schema)


@router.post("/create/request", status_code=201)
async def create_request(
    schema: CreateCourseObjectivesAndAudienceSchema = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: CourseService = Depends(get_course_service),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_request_async(schema)


@router.post("/create/student_target", status_code=201)
async def create_student_target(
    schema: CreateCourseObjectivesAndAudienceSchema = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: CourseService = Depends(get_course_service),
):
    await authorization.require_role(["LECTURER"])
    return await service.create_student_target_async(schema)
