import os

import isodate
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
    """
    Upload video lên YouTube (OAuth2)
    - Tự xác thực, lưu token.json để tái sử dụng
    - Upload video với privacyStatus = 'unlisted'
    - Sau khi upload, truy vấn metadata để lấy duration (tính bằng giây)
    """

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(
        self,
        client_secret_path: str = "app/core/secret/client_secret.json",
        token_path: str = "app/core/secret/token.json",
    ):
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        """Tự động xác thực / refresh token nếu có"""
        creds = None

        # Đọc token cũ nếu có
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        # Nếu chưa có hoặc token hết hạn
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("🔄 Token đã được refresh.")
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, self.SCOPES
                )
                creds = flow.run_local_server(port=8080, prompt="consent")

            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def upload(
        self,
        file_path: str,
        title: str,
        description: str = "",
        privacy: str = "unlisted",
    ) -> dict:
        """Upload video lên YouTube và trả về {video_id, url, duration_seconds}"""
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["elearning", "lesson"],
                "categoryId": "27",  # Education
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        print(f"🚀 Đang upload video: {os.path.basename(file_path)}")

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = request.execute()

        video_id = response.get("id")
        video_url = self.get_video_url(video_id)
        print(f"✅ Upload thành công: {video_url}")

        # 🔍 Lấy duration
        duration_seconds = self.get_duration(video_id)
        print(f"🕒 Thời lượng video: {duration_seconds:.0f} giây")

        return {
            "video_id": video_id,
            "video_url": video_url,
            "duration_seconds": duration_seconds,
        }

    def get_duration(self, video_id: str) -> float:
        """Lấy thời lượng video (tính bằng giây)"""
        response = (
            self.service.videos().list(part="contentDetails", id=video_id).execute()
        )
        items = response.get("items", [])
        if not items:
            return 0.0

        # Chuỗi thời lượng ISO 8601: ví dụ 'PT1H2M13S'
        duration_iso = items[0]["contentDetails"]["duration"]
        duration = isodate.parse_duration(duration_iso)
        return duration.total_seconds()

    def delete(self, video_id: str) -> bool:
        """Xóa video"""
        try:
            self.service.videos().delete(id=video_id).execute()
            print(f"🗑️ Đã xóa video: {video_id}")
            return True
        except Exception as e:
            print(f"❌ Lỗi khi xóa video: {e}")
            return False

    @staticmethod
    def get_video_url(video_id: str) -> str:
        """Trả về URL xem video"""
        return f"https://www.youtube.com/watch?v={video_id}"


# === Test nhanh ===
if __name__ == "__main__":
    uploader = YouTubeUploader(
        client_secret_path="app/core/secret/client_secret.json",
        token_path="app/core/secret/token.json",
    )

    video_path = "lesson01.mp4"
    result = uploader.upload(
        file_path=video_path,
        title="Bài học 01 - Python cơ bản",
        description="Giới thiệu Python, biến, kiểu dữ liệu, và ví dụ đầu tiên.",
    )

    print("\n📦 Kết quả trả về:")
    print(result)
