from enum import Enum


class FileEntity(str, Enum):
    """Phân loại nhóm dữ liệu chính trong hệ thống."""
    USER = "users"
    COURSE = "courses"
    SYSTEM = "system"


class FileType(str, Enum):
    """Phân loại loại file chi tiết."""
    AVATAR = "avatar"          # ảnh đại diện user
    UPLOADS = "uploads"        # user tự upload (bài tập, file nộp)
    VIDEOS = "videos"          # video bài học
    THUMBNAILS = "thumbnails"  # ảnh thumbnail khóa học
    ATTACHMENTS = "attachments"  # tài liệu bổ trợ (PDF, zip, pptx)
    IMAGES = "images"          # ảnh minh họa nội dung khóa học
