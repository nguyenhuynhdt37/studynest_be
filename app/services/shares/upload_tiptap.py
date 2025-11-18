import uuid

from fastapi import HTTPException, UploadFile

from app.services.shares.google_driver import GoogleDriveAsyncService


class UploadTiptapService:
    def __init__(self):
        pass

    async def upload_image_async(
        self,
        user_id: uuid.UUID,
        file: UploadFile,
        google_drive_service: GoogleDriveAsyncService,
        role: str,
    ):
        # Implementation to get user profile by user_id
        try:

            file_url = await google_drive_service.upload_file(
                [f"shares/{role}", str(object=user_id)],
                file.filename or f"picture_{user_id}_{uuid.uuid4()}_{uuid.uuid4()}.png",
                await file.read(),
                file.content_type,
            )
            return file_url.get("webViewLink", None)
        except Exception as e:

            raise HTTPException(status_code=500, detail=f"error {e}")
