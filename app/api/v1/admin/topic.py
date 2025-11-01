from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.admin.topic import TopicCreate, TopicUpdate
from app.services.admin.topic import TopicService

router = APIRouter(prefix="/admin/topics", tags=["Topics"])


# ✅ Inject TopicService chuẩn
def get_topic_service(
    topic_service: TopicService = Depends(TopicService),
) -> TopicService:
    return topic_service


# ✅ Inject RoleService chuẩn
def get_authorization_service(
    auth_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return auth_service


@router.post("", summary="Thêm topic mới")
async def create_topic(
    schema: TopicCreate,
    background_tasks: BackgroundTasks,
    service: TopicService = Depends(get_topic_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.create_topic_async(schema, background_tasks)


@router.get("", summary="lay topic topic mới")
async def get_topics(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("order_index"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    service: TopicService = Depends(get_topic_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_topics_async(
        page, limit, category_id, is_active, search, sort_by, sort_order
    )


@router.delete("/{topic_id}", summary="Xóa topic theo ID")
async def delete_topic(
    topic_id: UUID,
    service: TopicService = Depends(get_topic_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.delete_topic_async(topic_id)


@router.put("/{topic_id}", summary="Cập nhật topic theo ID")
async def update_topic(
    topic_id: UUID,
    schema: TopicUpdate,
    background_tasks: BackgroundTasks,
    service: TopicService = Depends(get_topic_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.update_topic_async(topic_id, schema, background_tasks)


@router.get("/{topic_id}", summary="Lấy thông tin topic theo ID")
async def get_topic(
    topic_id: UUID,
    service: TopicService = Depends(get_topic_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    await authorization.require_role(["ADMIN"])
    return await service.get_topic_by_id_async(topic_id)
