import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NotificationCreateSchema(BaseModel):
    """
    Schema tạo thông báo mới.
    - Dùng khi backend muốn tạo thông báo (ví dụ nạp tiền thành công, khóa học mới, v.v.)
    """

    user_id: Optional[uuid.UUID] = Field(
        default=None, description="ID người nhận thông báo (nếu gửi riêng)"
    )

    roles: Optional[List[str]] = None

    title: str = Field(..., description="Tiêu đề thông báo hiển thị cho người dùng")

    content: Optional[str] = Field(
        default=None, description="Nội dung chi tiết của thông báo"
    )

    url: Optional[str] = Field(
        default=None,
        description="Đường dẫn frontend khi người dùng click (VD: /wallet/history)",
    )

    type: Optional[str] = Field(
        default="system",
        description="Loại thông báo (system, wallet, course, alert, ...)",
    )

    role_target: Optional[List[str]] = Field(
        default_factory=list,
        description="Danh sách vai trò mục tiêu (VD: ['lecturer', 'admin'] hoặc ['all'])",
    )

    metadata: Optional[Dict] = Field(
        default_factory=dict, description="Dữ liệu phụ (VD: {'transaction_id': '...'} )"
    )

    action: Optional[str] = Field(
        default="open_url",
        description="Hành động của thông báo ('open_url', 'approve', 'confirm', ...)",
    )
