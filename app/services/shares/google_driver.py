import json
import os
from typing import Any, Dict, List, Optional

import aiofiles
import httpx
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

from app.core.settings import settings


class GoogleDriveAsyncService:
    """
    Phiên bản async-native của Google Drive Service (upload, share, folder).
    Dùng factory async để khởi tạo thay vì async __init__.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/youtube",
    ]

    TOKEN_PATH = "app/core/secret/token.json"
    CLIENT_SECRET_PATH = "app/core/secret/client_secret.json"

    # ✅ __init__ phải luôn đồng bộ
    def __init__(self, creds: Optional[Credentials] = None):
        self.api_key = settings.GOOGLE_API_KEY
        self.base_url = "https://www.googleapis.com/drive/v3"
        self.upload_url = "https://www.googleapis.com/upload/drive/v3/files"
        self.creds = creds
        self._access_token: Optional[str] = creds.token if creds else None

    # ===========================================================
    # 🏭 Factory method (chuẩn để khởi tạo async)
    # ===========================================================
    @classmethod
    async def create(cls) -> "GoogleDriveAsyncService":
        """Factory method async-safe."""
        self = cls()
        await self._authenticate()
        return self

    # ===========================================================
    async def _authenticate(self):
        """Load hoặc refresh token, giống bên YouTubeAsyncService."""
        creds = None

        if os.path.exists(self.TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.TOKEN_PATH, self.SCOPES
                )
            except Exception as e:
                logger.warning(f"⚠️ Token lỗi hoặc sai định dạng: {e}")
                creds = None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("🔄 Token Google Drive đã được refresh.")
            except RefreshError as e:
                logger.warning(f"⚠️ Refresh token không hợp lệ, cần xác thực lại: {e}")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(self.CLIENT_SECRET_PATH):
                raise RuntimeError(
                    "❌ Thiếu file client_secret.json để xác thực Google OAuth."
                )

            logger.info(
                "🆕 Đang chạy xác thực Google OAuth lần đầu (Drive + YouTube)..."
            )
            flow = InstalledAppFlow.from_client_secrets_file(
                self.CLIENT_SECRET_PATH, self.SCOPES
            )
            creds = flow.run_local_server(port=8080, prompt="consent")
            logger.success("✅ Xác thực thành công!")

        # giữ refresh_token cũ nếu cần
        token_data = creds.to_json()
        if '"refresh_token":' not in token_data and os.path.exists(self.TOKEN_PATH):
            with open(self.TOKEN_PATH, "r") as f:
                old = json.load(f)
                if "refresh_token" in old:
                    new = json.loads(token_data)
                    new["refresh_token"] = old["refresh_token"]
                    token_data = json.dumps(new)

        os.makedirs(os.path.dirname(self.TOKEN_PATH) or ".", exist_ok=True)
        with open(self.TOKEN_PATH, "w") as f:
            f.write(token_data)

        self.creds = creds
        self._access_token = creds.token
        logger.info("💾 Token Google Drive đã được lưu thành công.")

    # ===========================================================
    async def _get_access_token(self) -> str:
        """Trả về access_token, refresh nếu cần."""
        if self._access_token:
            return self._access_token

        creds = self.creds
        if creds.expired and creds.refresh_token:
            logger.info("🔄 Refreshing expired access token...")
            creds.refresh(Request())
            async with aiofiles.open(self.TOKEN_PATH, "w") as f:
                await f.write(creds.to_json())
        elif not creds.valid:
            raise RuntimeError("❌ Token không hợp lệ, cần xác thực lại.")

        self._access_token = creds.token
        return self._access_token

    # ===========================================================
    async def ensure_folder(self, path: str) -> str:
        """Đảm bảo thư mục tồn tại, tạo mới nếu thiếu."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        parts = path.strip("/").split("/")
        parent_id = None

        async with httpx.AsyncClient(timeout=60) as client:
            for name in parts:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                if parent_id:
                    query += f" and '{parent_id}' in parents"

                r = await client.get(
                    f"{self.base_url}/files",
                    headers=headers,
                    params={"q": query, "fields": "files(id,name)"},
                )
                folders = r.json().get("files", [])
                if folders:
                    parent_id = folders[0]["id"]
                else:
                    meta = {
                        "name": name,
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                    if parent_id:
                        meta["parents"] = [parent_id]
                    r = await client.post(
                        f"{self.base_url}/files", headers=headers, data=json.dumps(meta)
                    )
                    parent_id = r.json().get("id")

        return parent_id

    # ===========================================================
    async def upload_file(
        self,
        path_parts: List[str],
        file_name: str,
        content: bytes,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload file ≤ 2GB (async-native, multipart)."""
        folder_path = "Elearn_Uploader/" + "/".join(path_parts)
        folder_id = await self.ensure_folder(folder_path)
        access_token = await self._get_access_token()
        mime_type = mime_type or "application/octet-stream"

        if len(content) > 2 * 1024 * 1024 * 1024:
            raise ValueError("❌ File vượt quá giới hạn 2GB.")

        headers = {"Authorization": f"Bearer {access_token}"}
        metadata = {"name": file_name, "parents": [folder_id]}

        files = {
            "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
            "file": (file_name, content, mime_type),
        }

        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.upload_url}?uploadType=multipart", headers=headers, files=files
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"❌ Upload thất bại: {r.text}")

            data = r.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "webViewLink": f"https://drive.google.com/file/d/{data['id']}/view",
            }

    async def create_share_link(self, file_id: str) -> Dict[str, str]:
        """Cấp quyền public view + trả về các link hiển thị."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/files/{file_id}/permissions",
                headers=headers,
                data=json.dumps({"role": "reader", "type": "anyone"}),
            )

            if r.status_code not in (200, 201):
                raise RuntimeError(f"❌ Lỗi tạo permission: {r.text}")

        return {
            "view_link": f"https://drive.google.com/uc?id={file_id}",
            "thumbnail_link": f"https://drive.google.com/thumbnail?id={file_id}",
            "download_link": f"https://drive.google.com/uc?export=download&id={file_id}",
            "embed_link": f"https://drive.google.com/file/d/{file_id}/preview",
        }


# ============================================================
# ⚡ Singleton Provider cho FastAPI
# ============================================================

_google_drive_service: Optional[GoogleDriveAsyncService] = None


async def get_google_drive_service() -> GoogleDriveAsyncService:
    global _google_drive_service
    if _google_drive_service is None:
        logger.info("🚀 Khởi tạo GoogleDriveAsyncService lần đầu.")
        _google_drive_service = await GoogleDriveAsyncService.create()
    return _google_drive_service
