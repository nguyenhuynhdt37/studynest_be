import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from app.core.deps import AuthorizationService
from app.schemas.lecturer.courses import CreateCourse, UpdateCourse
from app.services.lecturer.course import CourseService

router = APIRouter(prefix="/lecturer/courses", tags=["Lecturer Course"])


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
    course_service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.get_courses_by_lecturer_async(
        lecturer.id, page, page_size, sort_by, is_published, search
    )


@router.get("/discount-targets")
async def get_courses_for_discount(
    authorization: AuthorizationService = Depends(AuthorizationService),
    course_service: CourseService = Depends(CourseService),
    search: str | None = None,
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.get_courses_for_discount_async(
        lecturer=lecturer, search=search
    )


@router.post("/create", status_code=status.HTTP_200_OK)
async def createCourses(
    background_tasks: BackgroundTasks,
    course_service: CourseService = Depends(CourseService),
    schema: CreateCourse = Body(),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.create_course_async(lecturer, schema, background_tasks)


@router.post("/upload-thumbnail/{course_id}")
async def upload_course_thumbnail(
    course_id: str,
    file: UploadFile = File(...),
    course_service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    await authorization.require_role(["LECTURER"])
    return await course_service.upload_thumbnail_async(course_id=course_id, file=file)


@router.get("/is_lecturer")
async def is_lecturer(
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    await authorization.require_role(["LECTURER"])
    return {"is_lecturer": True}


@router.get("/{course_id}/students")
async def lecturer_get_students(
    course_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    search: str | None = None,
    min_progress: float | None = None,
    max_progress: float | None = None,
    status: str | None = None,  # not_started / learning / almost / completed
    sort_by: str = "enrolled_at",
    order_dir: str = "desc",
    service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):

    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_course_students_list_async(
        course_id=course_id,
        instructor_id=lecturer.id,
        page=page,
        limit=limit,
        search=search,
        min_progress=min_progress,
        max_progress=max_progress,
        status=status,
        sort_by=sort_by,
        order_dir=order_dir,
    )


@router.get("/{course_id}/students/export")
async def lecturer_export_students_csv(
    course_id: uuid.UUID,
    search: str | None = None,
    min_progress: float | None = None,
    max_progress: float | None = None,
    status: str | None = None,
    sort_by: str = "enrolled_at",
    order_dir: str = "desc",
    service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    csv_data = await service.export_course_students_csv_async(
        course_id=course_id,
        instructor_id=lecturer.id,
        search=search,
        min_progress=min_progress,
        max_progress=max_progress,
        status=status,
        sort_by=sort_by,
        order_dir=order_dir,
    )

    filename = f"students_course_{course_id}.csv"
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{course_id}/students/stats")
async def lecturer_get_students_stats(
    course_id: uuid.UUID,
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: CourseService = Depends(CourseService),
):
    lecturer = await authorization.require_role(["LECTURER"])

    return await service.get_course_full_stats_async(
        course_id=course_id,
        instructor_id=lecturer.id,
    )


@router.get("/{course_id}/students/timeline")
async def lecturer_get_timeline_pro(
    course_id: uuid.UUID,
    mode: str = Query("day", regex="^(day|month|quarter|year)$"),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: CourseService = Depends(CourseService),
):

    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_course_activity_timeline_pro_async(
        course_id=course_id,
        instructor_id=lecturer.id,
        mode=mode,
    )


@router.get("/{course_id}/students/{student_id}")
async def lecturer_get_course_student_detail(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.require_role(["LECTURER"])
    return await service.get_course_student_detail_async(
        course_id=course_id,
        student_id=student_id,
        instructor_id=user.id,
    )


@router.get("/{course_id}", status_code=status.HTTP_200_OK)
async def get_course_detail(
    course_id: str,
    course_service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.get_course_detail_async(course_id, lecturer.id)


@router.put("/{course_id}", status_code=status.HTTP_200_OK)
async def update_course(
    course_id: str,
    background_tasks: BackgroundTasks,
    schema: UpdateCourse = Body(...),
    course_service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.update_course_async(
        course_id, lecturer.id, schema, background_tasks
    )


@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
async def delete_course(
    course_id: uuid.UUID,
    course_service: CourseService = Depends(CourseService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    lecturer = await authorization.require_role(["LECTURER"])
    return await course_service.delete_course_async(course_id, lecturer.id)
