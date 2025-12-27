from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class ChatImageSchema(BaseModel):
    url: str
    file_size: int = 0
    mime_type: Optional[str] = None
    ocr_text: str = ""
    drive_id: Optional[str] = None


class SendMessageSchema(BaseModel):
    message: str
    thread_id: Optional[UUID] = None
    images: Optional[List[ChatImageSchema]] = None
