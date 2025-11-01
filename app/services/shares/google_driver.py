import asyncio
import io
import os
from typing import Any, Dict, Optional

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.core.settings import settings

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveService:
    """Service xử lý upload + chia sẻ Google Drive (tối ưu cho file lớn, video/ảnh)."""

    _service_cache = None

    def __init__(self):
        self.client_secret_path = "app/core/secret/client_secret.json"
        self.token_path = "app/core/secret/token.json"
        self.api_key = settings.GOOGLE_API_KEY

    # ---------- AUTH ----------
    def _get_credentials(self):
        """Xác thực OAuth2 cho Google Drive."""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                creds = flow.run_local_server(port=8080, prompt="consent")
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def _get_service(self):
        """Khởi tạo Google Drive service (dùng cache để tiết kiệm)."""
        if GoogleDriveService._service_cache is None:
            creds = self._get_credentials()
            GoogleDriveService._service_cache = build("drive", "v3", credentials=creds)
        return GoogleDriveService._service_cache

    # ---------- FOLDER ----------
    async def ensure_folder(self, path: str) -> str:
        """Đảm bảo thư mục tồn tại trên Drive, trả về folder_id."""
        service = self._get_service()
        parts = path.strip("/").split("/")
        parent_id = None
        loop = asyncio.get_event_loop()

        def _ensure():
            nonlocal parent_id
            for name in parts:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                if parent_id:
                    query += f" and '{parent_id}' in parents"

                results = (
                    service.files().list(q=query, fields="files(id,name)").execute()
                )
                folders = results.get("files", [])
                if folders:
                    parent_id = folders[0]["id"]
                else:
                    meta = {
                        "name": name,
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                    if parent_id:
                        meta["parents"] = [parent_id]
                    folder = service.files().create(body=meta, fields="id").execute()
                    parent_id = folder["id"]
            return parent_id

        return await loop.run_in_executor(None, _ensure)

    # ---------- UPLOAD ----------
    async def upload_file(
        self,
        path_parts: list[str],
        file_name: str,
        content: bytes,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload file lên Google Drive (hỗ trợ file lớn ≤ 2GB, resumable upload).
        """
        service = self._get_service()
        base_path = "Elearn_Uploader/" + "/".join(path_parts)
        folder_id = await self.ensure_folder(base_path)

        # 🔒 Giới hạn kích thước tối đa
        MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
        if len(content) > MAX_SIZE_BYTES:
            raise ValueError("❌ File vượt quá giới hạn 2GB cho phép.")

        # Mặc định auto MIME nếu không có
        mime_type = mime_type or "application/octet-stream"

        file_meta = {"name": file_name, "parents": [folder_id]}

        # Dùng resumable upload để tránh timeout khi mạng yếu
        media = MediaIoBaseUpload(
            io.BytesIO(content), mimetype=mime_type, resumable=True
        )

        loop = asyncio.get_event_loop()

        def _upload():
            try:
                return (
                    service.files()
                    .create(
                        body=file_meta,
                        media_body=media,
                        fields="id, name",
                    )
                    .execute(num_retries=3)
                )
            except Exception as e:
                raise RuntimeError(f"❌ Upload thất bại: {e}")

        return await loop.run_in_executor(None, _upload)

    # ---------- SHARE LINK ----------
    async def create_share_link(self, file_id: str) -> Dict[str, str]:
        """Tạo link chia sẻ hiển thị được trên Next.js (ảnh/video)."""
        service = self._get_service()
        loop = asyncio.get_event_loop()

        def _share():
            try:
                try:
                    service.permissions().create(
                        fileId=file_id,
                        body={"role": "reader", "type": "anyone"},
                        fields="id",
                    ).execute()
                except HttpError as e:
                    if e.resp.status != 403:
                        raise

                # Link hiển thị trực tiếp (ảnh/video)
                return {
                    "view_link": f"https://drive.google.com/uc?id={file_id}",
                    "thumbnail_link": f"https://drive.google.com/thumbnail?id={file_id}",
                    "download_link": f"https://drive.google.com/uc?export=download&id={file_id}",
                    "embed_link": f"https://drive.google.com/file/d/{file_id}/preview",
                }

            except Exception as e:
                raise RuntimeError(f"❌ Lỗi tạo link chia sẻ: {e}")

        return await loop.run_in_executor(None, _share)

    # ---------- VIDEO DURATION ----------
    async def get_google_drive_video_duration_async(
        self, file_id: str
    ) -> Optional[float]:
        """Lấy thời lượng video (giây) từ metadata của Google Drive."""
        if not self.api_key:
            raise RuntimeError("Missing GOOGLE_API_KEY in environment variables.")

        url = (
            f"https://www.googleapis.com/drive/v3/files/{file_id}"
            f"?fields=videoMediaMetadata&key={self.api_key}"
        )

        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.get(url)
            if res.status_code != 200:
                return None

            data = res.json()
            meta = data.get("videoMediaMetadata", {})
            duration_ms = int(meta.get("durationMillis", 0))
            return round(duration_ms / 1000, 2) if duration_ms else None
