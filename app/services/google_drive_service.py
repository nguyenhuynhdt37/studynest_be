# app/services/google_drive_service.py
import os

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.core.settings import settings


class GoogleDriveService:
    @staticmethod
    async def get_google_drive_video_duration_async(file_id: str) -> float | None:
        """
        Lấy thời lượng video (giây) từ Google Drive API.
        Trả về None nếu không lấy được hoặc file không phải video.
        """
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise RuntimeError("Missing GOOGLE_API_KEY in environment variables.")

        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=videoMediaMetadata&key={api_key}"

        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            if res.status_code != 200:
                return None

            data = res.json()
            meta = data.get("videoMediaMetadata", {})
            duration_ms = int(meta.get("durationMillis", 0))
            if duration_ms == 0:
                return None

            return round(duration_ms / 1000, 2)  # giây
