import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, UploadFile, status

from app.core.deps import AuthorizationService
from app.schemas.lecturer.courses import CreateCourse, UpdateCourse
from app.services.lecturer.course import CourseService
from app.services.user.category import CategoryService

router = APIRouter(prefix="/lecturer/courses", tags=["Lecturer Course"])


def get_course_service(
    course_service: CourseService = Depends(CourseService),
) -> CourseService:
    return course_service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


def get_category_service(
    category_service: CategoryService = Depends(CategoryService),
) -> CategoryService:
    return category_service


@router.get("", status_code=status.HTTP_200_OK)
async def getCategory(
    lecturer_id: str,
    page: int = 1,
    page_size: int = 10,
    sort_by: Optional[
        str
    ] = "revenue",  # revenue | created_at | views | enrolls | rating
    is_published: Optional[bool] = None,
    search: Optional[str] = None,
    course_service: CourseService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.get_courses_by_lecturer_async(
        lecturer.id, page, page_size, sort_by, is_published, search
    )


@router.post("/create", status_code=status.HTTP_200_OK)
async def createCourses(
    background_tasks: BackgroundTasks,
    course_service: CourseService = Depends(get_course_service),
    schema: CreateCourse = Body(),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.create_course_async(lecturer, schema, background_tasks)


@router.post("/upload-thumbnail/{course_id}")
async def upload_course_thumbnail(
    course_id: str,
    file: UploadFile = File(...),
    course_service: CourseService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["LECTURER"])
    return await course_service.upload_thumbnail_async(course_id=course_id, file=file)


@router.get("/is_lecturer")
async def is_lecturer(
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["LECTURER"])
    return {"is_lecturer": True}


@router.get("/{course_id}", status_code=status.HTTP_200_OK)
async def get_course_detail(
    course_id: str,
    course_service: CourseService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.get_course_detail_async(course_id, lecturer.id)


@router.put("/{course_id}", status_code=status.HTTP_200_OK)
async def update_course(
    course_id: str,
    background_tasks: BackgroundTasks,
    schema: UpdateCourse = Body(...),
    course_service: CourseService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.update_course_async(
        course_id, lecturer.id, schema, background_tasks
    )


@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
async def delete_course(
    course_id: uuid.UUID,
    course_service: CourseService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.delete_course_async(course_id, lecturer.id)
