from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.chat.admin.topic import CreateDetailsTopic
from app.services.chat.admin.topic import TopicService

router = APIRouter(prefix="/admin/chat/topics", tags=["CHAT ADMIN TOPICS"])


def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


def get_topic_service(
    topic_service: TopicService = Depends(TopicService),
) -> TopicService:
    return topic_service


@router.post("/create/description", status_code=201)
async def create_category_description(
    schema: CreateDetailsTopic = Body(...),
    authorization: AuthorizationService = Depends(get_authorization_service),
    service: TopicService = Depends(get_topic_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.create_topic_details_async(schema)
