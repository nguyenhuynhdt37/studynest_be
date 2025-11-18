from fastapi import APIRouter, Body, Depends

from app.core.deps import AuthorizationService  # class chứa require_role
from app.schemas.chat.user.profile import CreateBioSchema
from app.services.chat.user.profile import ProfileService

router = APIRouter(prefix="/user/chat/profile", tags=["CHAT USER PROFILE"])


@router.post("/create_bio", status_code=201)
async def create_bio(
    schema: CreateBioSchema = Body(...),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: ProfileService = Depends(ProfileService),
):
    user = await authorization.require_role(["USER"])
    return await service.create_bio_async(schema, user)
