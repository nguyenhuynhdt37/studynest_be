from fastapi import APIRouter, Body, Depends, status

from app.core.deps import AuthorizationService
from app.schemas.user.learning_fields import LearningFielsSave
from app.services.user.user_preferences import UserPreferencesService

router = APIRouter(prefix="/user_preferences", tags=["Learning Fields"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def save_user_learning_preferences(
    user_preferences_service: UserPreferencesService = Depends(UserPreferencesService),
    schema: LearningFielsSave = Body(),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await user_preferences_service.save_user_learning_preferences_async(
        schema, user
    )
