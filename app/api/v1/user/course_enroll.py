import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.user.course_enroll import CourseEnrolls

router = APIRouter(prefix="/purchases", tags=["User Course Enrollments"])


@router.get("/courses")
async def get_my_courses(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    category_id: uuid.UUID | None = None,
    level: str | None = None,
    language: str | None = None,
    sort_by: str = Query(
        "created_at", description="created_at, rating_avg, views, progress"
    ),
    order: str = Query("desc", description="asc hoặc desc"),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    purchase_service: CourseEnrolls = Depends(CourseEnrolls),
):
    user: User = await authorization_service.get_current_user()
    return await purchase_service.get_user_courses_async(
        user.id, page, size, keyword, category_id, level, language, sort_by, order
    )


@router.get("/courses/user/{user_id}")
async def get_user_courses(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    category_id: uuid.UUID | None = None,
    level: str | None = None,
    language: str | None = None,
    sort_by: str = Query(
        "created_at", description="created_at, rating_avg, views, progress"
    ),
    order: str = Query("desc", description="asc hoặc desc"),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    purchase_service: CourseEnrolls = Depends(CourseEnrolls),
):
    await authorization_service.get_current_user()
    return await purchase_service.get_user_courses_async(
        user_id, page, size, keyword, category_id, level, language, sort_by, order
    )
