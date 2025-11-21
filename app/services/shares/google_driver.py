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
    Async Google Drive Service (Upload + Share)
    Có log kiểm tra permission để phát hiện lỗi chặn chia sẻ.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/youtube",
    ]

    TOKEN_PATH = "app/core/secret/token.json"
    CLIENT_SECRET_PATH = "app/core/secret/client_secret.json"

    def __init__(self, creds: Optional[Credentials] = None):
        self.api_key = settings.GOOGLE_API_KEY
        self.base_url = "https://www.googleapis.com/drive/v3"
        self.upload_url = "https://www.googleapis.com/upload/drive/v3/files"
        self.creds = creds
        self._access_token: Optional[str] = creds.token if creds else None

    # ===========================================================
    @classmethod
    async def create(cls) -> "GoogleDriveAsyncService":
        self = cls()
        await self._authenticate()
        return self

    # ===========================================================
    async def _authenticate(self):
        """Tự động load token, tự refresh nếu hết hạn. Chỉ yêu cầu OAuth khi không còn refresh_token hợp lệ."""
        creds = None

        # 1) Load token JSON nếu có
        if os.path.exists(self.TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.TOKEN_PATH, self.SCOPES
                )
                logger.info("🔑 Đã load token Google thành công.")
            except Exception as e:
                logger.warning(f"⚠️ Token lỗi: {e}")
                creds = None

        # 2) Nếu có token + có refresh_token → tự refresh
        if creds and creds.refresh_token:
            if creds.expired:
                try:
                    logger.info("🔄 Token hết hạn → đang refresh access_token...")
                    creds.refresh(Request())
                    await self._save_token(creds)
                    self.creds = creds
                    self._access_token = creds.token
                    return
                except RefreshError as e:
                    logger.warning(f"⚠️ Refresh token không hợp lệ: {e}")
                    creds = None  # buộc xác thực lại

            else:
                # Token chưa hết hạn
                logger.info("🔐 Token hợp lệ, không cần xác thực lại.")
                self.creds = creds
                self._access_token = creds.token
                return

        # 3) Nếu không có refresh_token → yêu cầu OAuth 1 lần
        logger.info("🆕 Không có refresh_token → chạy Google OAuth lần đầu...")
        flow = InstalledAppFlow.from_client_secrets_file(
            self.CLIENT_SECRET_PATH, self.SCOPES
        )
        creds = flow.run_local_server(port=8080, prompt="consent")

        await self._save_token(creds)
        self.creds = creds
        self._access_token = creds.token

        logger.success("✅ Xác thực Google Drive thành công!")

    async def _save_token(self, creds: Credentials):
        """Lưu token + refresh_token vào file JSON."""
        token_json = creds.to_json()
        os.makedirs(os.path.dirname(self.TOKEN_PATH), exist_ok=True)

        async with aiofiles.open(self.TOKEN_PATH, "w") as f:
            await f.write(token_json)

        logger.info("💾 Token Google Drive đã được lưu.")

    # ===========================================================
    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        creds = self.creds
        if creds.expired and creds.refresh_token:
            logger.info("🔄 Refresh token...")
            creds.refresh(Request())
            async with aiofiles.open(self.TOKEN_PATH, "w") as f:
                await f.write(creds.to_json())
        elif not creds.valid:
            raise RuntimeError("❌ Token không hợp lệ, cần xác thực lại.")

        self._access_token = creds.token
        return self._access_token

    # ===========================================================
    async def ensure_folder(self, path: str) -> str:
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

        folder_path = "Elearn_Uploader/" + "/".join(path_parts)
        folder_id = await self.ensure_folder(folder_path)

        access_token = await self._get_access_token()
        mime_type = mime_type or "application/octet-stream"

        if len(content) > 2 * 1024 * 1024 * 1024:
            raise ValueError("❌ File vượt quá 2GB.")

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

    # ===========================================================
    async def create_share_link(self, file_id: str) -> Dict[str, str]:
        """
        Tạo link xem công khai (anyone).
        Có kiểm tra permission để biết Google có CHẶN share hay không.
        """

        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Tạo permission public
            r = await client.post(
                f"{self.base_url}/files/{file_id}/permissions",
                headers=headers,
                data=json.dumps({"role": "reader", "type": "anyone"}),
            )

            if r.status_code not in (200, 201):
                raise RuntimeError(f"❌ Lỗi tạo permission: {r.text}")

            # ❗ Kiểm tra permission thực sự
            check = await client.get(
                f"{self.base_url}/files/{file_id}",
                headers=headers,
                params={"fields": "permissions,owners"},
            )
            perm_info = check.json()

            logger.info("📌 Kiểm tra permission sau khi cấp:")
            logger.info(json.dumps(perm_info, indent=2))

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
