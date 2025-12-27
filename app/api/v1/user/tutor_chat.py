# app/api/v1/user/tutor_chat.py
"""
API endpoints cho Tutor Chat Threads.

REST API Convention:
- GET    /lessons/{id}/threads      - List threads
- GET    /lessons/{id}/threads/active - Get active thread
- POST   /lessons/{id}/threads      - Create new thread
- GET    /threads/{id}              - Get thread detail
- PATCH  /threads/{id}              - Update thread (choose active)
- DELETE /threads/{id}              - Delete thread
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.schemas.chat.user.tutor_chat import SendMessageSchema
from app.services.user.tutor_chat import TutorChatService, get_tutor_chat_service
from app.services.user.tutor_chat_message import (
    TutorChatMessageService,
    get_tutor_chat_message_service,
)

router = APIRouter(prefix="/tutor-chat", tags=["User Tutor Chat"])


# =========================
# REQUEST/RESPONSE MODELS
# =========================


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    is_active: Optional[bool] = None
    title: Optional[str] = None
    scope: Optional[str] = None  # 'lesson' | 'section' | 'course'


# =========================
# LESSON THREADS ENDPOINTS
# =========================


@router.get("/lessons/{lesson_id}/threads")
async def list_threads(
    lesson_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None, alias="cursor_next"),
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Lấy danh sách threads của lesson.
    Cursor-based pagination, sắp xếp theo updated_at DESC.
    """
    user: User = await auth.get_current_user()
    return await service.get_threads_by_lesson(
        user_id=user.id,
        lesson_id=lesson_id,
        limit=limit,
        cursor_next=cursor,
    )


@router.get("/lessons/{lesson_id}/threads/active")
async def get_active_thread(
    lesson_id: uuid.UUID,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Lấy thread đang active của lesson.
    Returns null nếu không có.
    """
    user: User = await auth.get_current_user()
    thread = await service.get_active_thread(
        user_id=user.id,
        lesson_id=lesson_id,
    )
    return {"thread": thread}


@router.post("/lessons/{lesson_id}/threads")
async def create_thread(
    lesson_id: uuid.UUID,
    body: Optional[CreateThreadRequest] = None,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Tạo thread mới cho lesson.
    - Deactivate tất cả threads khác
    - Set thread mới là active
    - Title mặc định: "New chat"
    """
    user: User = await auth.get_current_user()
    title = body.title if body else None
    thread = await service.create_new_thread(
        user_id=user.id,
        lesson_id=lesson_id,
        title=title,
    )
    return {"thread": thread}


# =========================
# THREAD RESOURCE ENDPOINTS
# =========================


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: uuid.UUID,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Lấy chi tiết thread.
    """
    user: User = await auth.get_current_user()
    thread = await service.get_thread_by_id(
        user_id=user.id,
        thread_id=thread_id,
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread": thread}


@router.patch("/threads/{thread_id}")
async def update_thread(
    thread_id: uuid.UUID,
    body: UpdateThreadRequest,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Cập nhật thread.
    - is_active=true: Set làm active, deactivate các thread khác
    - is_active=false: Deactivate thread này
    - title: Đổi tiêu đề
    - scope: Thay đổi scope ('lesson' | 'section' | 'course')
    """
    user: User = await auth.get_current_user()

    # Nếu set active
    if body.is_active is True:
        thread = await service.choose_thread(
            user_id=user.id,
            thread_id=thread_id,
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"thread": thread}

    # Nếu deactivate
    if body.is_active is False:
        success = await service.deactivate_thread(
            user_id=user.id,
            thread_id=thread_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"success": True}

    # Update title hoặc scope
    if body.title is not None or body.scope is not None:
        # Validate scope
        if body.scope and body.scope not in ["lesson", "section", "course"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid scope. Must be 'lesson', 'section', or 'course'",
            )

        thread = await service.update_thread(
            user_id=user.id,
            thread_id=thread_id,
            title=body.title,
            scope=body.scope,
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"thread": thread}

    return {"success": True}


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: uuid.UUID,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatService = Depends(get_tutor_chat_service),
):
    """
    Xóa thread (soft delete).
    """
    user: User = await auth.get_current_user()
    success = await service.delete_thread(
        user_id=user.id,
        thread_id=thread_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"success": True}


# =========================
# MESSAGE ENDPOINTS
# =========================

# ... (imports)


@router.post("/upload/image")
async def upload_image_for_chat(
    file: UploadFile = File(...),
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Upload ảnh cho chat & OCR.
    1. Upload lên Google Drive
    2. OCR trích xuất text
    3. Trả về metadata để client gửi kèm message
    """
    user: User = await auth.get_current_user()

    # Delegate to service
    results = await service.upload_and_ocr_images(user_id=user.id, files=[file])

    if not results:
        raise HTTPException(status_code=400, detail="Upload failed or invalid file")

    return results[0]


@router.post("/lessons/{lesson_id}/chat")
async def send_message(
    lesson_id: uuid.UUID,
    body: SendMessageSchema,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Gửi tin nhắn chat.

    - Nếu không có thread_id → dùng active thread hoặc tạo mới
    - Có thể gửi kèm danh sách ảnh (images) đã upload trước đó
    - Trả về cả user message và assistant response
    """
    user: User = await auth.get_current_user()
    return await service.send_message(
        user_id=user.id,
        lesson_id=lesson_id,
        message=body.message,
        thread_id=body.thread_id,
        images=body.images,
    )


@router.get("/threads/{thread_id}/messages")
async def get_messages(
    thread_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    cursor_next: Optional[str] = Query(None),
    auth: AuthorizationService = Depends(AuthorizationService),
    service: TutorChatMessageService = Depends(get_tutor_chat_message_service),
):
    """
    Lấy danh sách messages của thread.
    Sắp xếp theo created_at ASC (cũ trước, mới sau).
    """
    user: User = await auth.get_current_user()
    return await service.get_messages(
        user_id=user.id,
        thread_id=thread_id,
        limit=limit,
        cursor_next=cursor_next,
    )
