from fastapi import APIRouter, Body, Depends, status

from app.core.deps import AuthorizationService
from app.schemas.user.learning_fields import LearningFielsSave
from app.services.user.learning_fields import LearningFieldService

router = APIRouter(prefix="/learning_fields", tags=["Learning Fields"])


@router.get("/", status_code=status.HTTP_200_OK)
async def getLearningFields(
    learning_field_service: LearningFieldService = Depends(LearningFieldService),
):
    return await learning_field_service.get_learning_fields_async()


@router.post("/save", status_code=status.HTTP_201_CREATED)
async def save_user_learning_preferences(
    learning_field_service: LearningFieldService = Depends(LearningFieldService),
    schema: LearningFielsSave = Body(),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_field_service.save_user_learning_preferences_async(
        schema, user
    )
