from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.chat.admin.topic import CreateDetailsTopic
from app.services.chat.admin.topic import TopicService

router = APIRouter(prefix="/admin/chat/topics", tags=["CHAT ADMIN TOPICS"])


@router.post("/create/description", status_code=201)
async def create_category_description(
    schema: CreateDetailsTopic = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: TopicService = Depends(TopicService),
):
    await authorization.require_role(["ADMIN"])
    return await service.create_topic_details_async(schema)
