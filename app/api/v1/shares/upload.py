from fastapi import APIRouter, Depends, File, UploadFile

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.shares.google_driver import (
    GoogleDriveAsyncService,
    get_google_drive_service,
)
from app.services.shares.upload_tiptap import UploadTiptapService

router = APIRouter(prefix="/upload", tags=["Uploads"])


@router.post("")
async def create_upload(
    file: UploadFile = File(...),
    upload: UploadTiptapService = Depends(UploadTiptapService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    google_drive_service: GoogleDriveAsyncService = Depends(get_google_drive_service),
):
    user: User = await authorization_service.get_current_user()
    return await upload.upload_image_async(
        user.id,
        file,
        google_drive_service,
        role="USER",
    )
