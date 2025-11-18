import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.user.favorites import CourseFavoriteService

router = APIRouter(prefix="/favourites", tags=["User Favorite"])


@router.post("/{course_id}")
async def toggle_favorite_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    favorite_service: CourseFavoriteService = Depends(CourseFavoriteService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await favorite_service.toggle_favorite_course_async(
        course_id, background_tasks, user
    )


@router.get("/{course_id}")
async def check_is_favorite_course(
    course_id: uuid.UUID,
    favorite_service: CourseFavoriteService = Depends(CourseFavoriteService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await favorite_service.check_is_favorite_course_async(course_id, user)


@router.get("")
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
    favorite_service: CourseFavoriteService = Depends(CourseFavoriteService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user: User = await authorization.get_current_user()
    return await favorite_service.get_user_favourite_courses_async(
        user.id, page, size, keyword, category_id, level, language, sort_by, order
    )
