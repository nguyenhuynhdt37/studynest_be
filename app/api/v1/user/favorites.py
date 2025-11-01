import uuid
from re import A

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.db.sesson import get_session
from app.services.user.favorites import CourseFavoriteService

router = APIRouter(prefix="/favourites", tags=["User Favorite"])


def get_favorite_service(
    service: CourseFavoriteService = Depends(CourseFavoriteService),
) -> CourseFavoriteService:
    return service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.post("/{course_id}")
async def toggle_favorite_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    favorite_service: CourseFavoriteService = Depends(get_favorite_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await favorite_service.toggle_favorite_course_async(
        course_id, background_tasks, user
    )


@router.get("/{course_id}")
async def check_is_favorite_course(
    course_id: uuid.UUID,
    favorite_service: CourseFavoriteService = Depends(get_favorite_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await favorite_service.check_is_favorite_course_async(course_id, user)
