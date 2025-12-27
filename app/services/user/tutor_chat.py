# app/services/user/tutor_chat.py
"""
TutorChatService - Quản lý tutor chat threads.

Chức năng:
- Lấy danh sách chat threads theo user + lesson
- Cursor-based pagination
- Kiểm tra enrollment trước khi truy cập
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import (
    CourseEnrollments,
    Courses,
    Lessons,
    TutorChatMessages,
    TutorChatThreads,
)
from app.db.sesson import get_session


class TutorChatService:
    """Service quản lý tutor chat threads."""

    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    # =========================
    # VALIDATION
    # =========================

    async def validate_enrollment(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """
        Kiểm tra user đã enroll khóa học chưa.
        Raises HTTPException nếu chưa enroll.
        """
        result = await self.db.execute(
            select(CourseEnrollments).where(
                CourseEnrollments.user_id == user_id,
                CourseEnrollments.course_id == course_id,
                CourseEnrollments.status == "active",
            )
        )
        enrollment = result.scalar_one_or_none()

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="You must enroll this course first",
            )

        return True

    async def validate_lesson_access(
        self,
        user_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Kiểm tra user có quyền truy cập lesson không.
        Returns lesson info nếu hợp lệ.
        """
        # Lấy lesson và course info
        result = await self.db.execute(
            select(Lessons, Courses)
            .join(Courses, Courses.id == Lessons.course_id)
            .where(Lessons.id == lesson_id)
        )
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Lesson not found")

        lesson, course = row

        # Kiểm tra enrollment (trừ preview lessons)
        if not lesson.is_preview:
            await self.validate_enrollment(user_id, course.id)

        return {
            "lesson": lesson,
            "course": course,
        }

    # =========================
    # THREAD OPERATIONS
    # =========================

    async def get_threads_by_lesson(
        self,
        user_id: uuid.UUID,
        lesson_id: uuid.UUID,
        limit: int = 10,
        cursor_next: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lấy danh sách chat threads theo user và lesson.

        Args:
            user_id: ID người dùng
            lesson_id: ID bài học
            limit: Số lượng threads (default 10, max 50)
            cursor_next: Cursor cho pagination (updated_at dạng ISO)

        Returns:
            {
                "threads": [...],
                "cursor_next": str | None,
                "has_more": bool,
            }
        """
        # Validate
        lesson_info = await self.validate_lesson_access(user_id, lesson_id)

        # Limit bounds
        limit = min(max(limit, 1), 50)

        # Build query
        query = (
            select(TutorChatThreads)
            .where(
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.lesson_id == lesson_id,
                TutorChatThreads.is_deleted.is_(False),
            )
            .order_by(desc(TutorChatThreads.updated_at))
        )

        # Apply cursor (cursor_next = updated_at của item cuối)
        if cursor_next:
            try:
                cursor_time = datetime.fromisoformat(cursor_next)
                query = query.where(TutorChatThreads.updated_at < cursor_time)
            except ValueError:
                pass  # Invalid cursor, ignore

        # Fetch limit + 1 để check has_more
        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        threads = result.scalars().all()

        # Check has_more
        has_more = len(threads) > limit
        if has_more:
            threads = threads[:limit]

        # Build cursor_next
        next_cursor = None
        if threads and has_more:
            last_thread = threads[-1]
            next_cursor = last_thread.updated_at.isoformat()

        # Count messages cho mỗi thread
        thread_ids = [t.id for t in threads]
        message_counts = {}
        if thread_ids:
            counts_result = await self.db.execute(
                select(
                    TutorChatMessages.thread_id,
                    func.count(TutorChatMessages.id).label("count"),
                )
                .where(TutorChatMessages.thread_id.in_(thread_ids))
                .group_by(TutorChatMessages.thread_id)
            )
            for row in counts_result:
                message_counts[row.thread_id] = row.count

        return {
            "threads": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "scope": t.scope,
                    "is_active": t.is_active,
                    "message_count": message_counts.get(t.id, 0),
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat(),
                }
                for t in threads
            ],
            "cursor_next": next_cursor,
            "has_more": has_more,
            "lesson": {
                "id": str(lesson_info["lesson"].id),
                "title": lesson_info["lesson"].title,
            },
            "course": {
                "id": str(lesson_info["course"].id),
                "title": lesson_info["course"].title,
            },
        }

    async def get_active_thread(
        self,
        user_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy thread đang active của user cho lesson.
        Mỗi user chỉ có 1 active thread per lesson.

        Returns:
            Thread info hoặc None nếu không có.
        """
        # Validate enrollment
        await self.validate_lesson_access(user_id, lesson_id)

        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.lesson_id == lesson_id,
                TutorChatThreads.is_active.is_(True),
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return None

        return {
            "id": str(thread.id),
            "title": thread.title,
            "scope": thread.scope,
            "is_active": thread.is_active,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "course_id": str(thread.course_id),
            "lesson_id": str(thread.lesson_id),
        }

    async def get_thread_by_id(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy thread theo ID.
        Chỉ trả về thread của user (ownership check).
        """
        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.id == thread_id,
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return None

        return {
            "id": str(thread.id),
            "title": thread.title,
            "scope": thread.scope,
            "is_active": thread.is_active,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "course_id": str(thread.course_id),
            "lesson_id": str(thread.lesson_id),
        }

    async def get_or_create_active_thread(
        self,
        user_id: uuid.UUID,
        lesson_id: uuid.UUID,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lấy thread active hiện tại hoặc tạo mới nếu chưa có.

        Returns:
            {
                "thread": {...},
                "is_new": bool,
            }
        """
        # Kiểm tra đã có active thread chưa
        existing = await self.get_active_thread(user_id, lesson_id)
        if existing:
            return {
                "thread": existing,
                "is_new": False,
            }

        # Lấy lesson info để có course_id
        lesson_info = await self.validate_lesson_access(user_id, lesson_id)
        course_id = lesson_info["course"].id

        # Tạo thread mới
        new_thread = TutorChatThreads(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            title=title or f"Chat - {lesson_info['lesson'].title}",
            scope="lesson",
            is_active=True,
            is_deleted=False,
        )
        self.db.add(new_thread)
        await self.db.commit()
        await self.db.refresh(new_thread)

        return {
            "thread": {
                "id": str(new_thread.id),
                "title": new_thread.title,
                "scope": new_thread.scope,
                "is_active": new_thread.is_active,
                "created_at": new_thread.created_at.isoformat(),
                "updated_at": new_thread.updated_at.isoformat(),
                "course_id": str(new_thread.course_id),
                "lesson_id": str(new_thread.lesson_id),
            },
            "is_new": True,
        }

    async def create_new_thread(
        self,
        user_id: uuid.UUID,
        lesson_id: uuid.UUID,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tạo thread mới và set active.
        Deactivate tất cả threads khác của user trong cùng lesson.

        Args:
            user_id: ID người dùng
            lesson_id: ID bài học
            title: Tiêu đề (mặc định "New chat")

        Returns:
            Thread info
        """
        # Validate lesson access
        lesson_info = await self.validate_lesson_access(user_id, lesson_id)
        course_id = lesson_info["course"].id

        # Deactivate tất cả threads hiện tại của user trong lesson
        current_threads = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.lesson_id == lesson_id,
                TutorChatThreads.is_active.is_(True),
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        for t in current_threads.scalars().all():
            t.is_active = False
            t.updated_at = datetime.utcnow()

        # Tạo thread mới với active = True
        new_thread = TutorChatThreads(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            title=title or "New chat",
            scope="lesson",
            is_active=True,
            is_deleted=False,
        )
        self.db.add(new_thread)
        await self.db.commit()
        await self.db.refresh(new_thread)

        return {
            "id": str(new_thread.id),
            "title": new_thread.title,
            "scope": new_thread.scope,
            "is_active": new_thread.is_active,
            "created_at": new_thread.created_at.isoformat(),
            "updated_at": new_thread.updated_at.isoformat(),
            "course_id": str(new_thread.course_id),
            "lesson_id": str(new_thread.lesson_id),
        }

    async def deactivate_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> bool:
        """
        Đánh dấu thread không còn active.
        User chỉ có thể deactivate thread của chính mình.
        """
        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.id == thread_id,
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return False

        thread.is_active = False
        thread.updated_at = datetime.utcnow()
        await self.db.commit()

        return True

    async def delete_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> bool:
        """
        Soft delete thread.
        User chỉ có thể xóa thread của chính mình.
        """
        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.id == thread_id,
                TutorChatThreads.user_id == user_id,
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return False

        thread.is_deleted = True
        thread.is_active = False
        thread.updated_at = datetime.utcnow()
        await self.db.commit()

        return True

    async def update_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        title: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Cập nhật thông tin thread (title, scope).

        Args:
            user_id: ID người dùng
            thread_id: ID thread
            title: Tiêu đề mới (optional)
            scope: Scope mới: 'lesson' | 'section' | 'course' (optional)

        Returns:
            Thread info sau khi update, hoặc None nếu không tìm thấy.
        """
        # Validate scope nếu có
        valid_scopes = ["lesson", "section", "course"]
        if scope and scope not in valid_scopes:
            return None

        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.id == thread_id,
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return None

        # Update fields
        if title is not None:
            thread.title = title
        if scope is not None:
            thread.scope = scope

        thread.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(thread)

        return {
            "id": str(thread.id),
            "title": thread.title,
            "scope": thread.scope,
            "is_active": thread.is_active,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "course_id": str(thread.course_id),
            "lesson_id": str(thread.lesson_id),
        }

    async def choose_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Chọn thread làm active.
        - Set thread được chọn thành active
        - Deactivate tất cả threads khác của user trong cùng lesson

        Returns:
            Thread info nếu thành công, None nếu không tìm thấy.
        """
        # Lấy thread được chọn
        result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.id == thread_id,
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.is_deleted.is_(False),
            )
        )
        thread = result.scalar_one_or_none()

        if not thread:
            return None

        # Deactivate tất cả threads khác của user trong cùng lesson
        other_threads_result = await self.db.execute(
            select(TutorChatThreads).where(
                TutorChatThreads.user_id == user_id,
                TutorChatThreads.lesson_id == thread.lesson_id,
                TutorChatThreads.id != thread_id,
                TutorChatThreads.is_deleted.is_(False),
                TutorChatThreads.is_active.is_(True),
            )
        )
        other_threads = other_threads_result.scalars().all()

        for t in other_threads:
            t.is_active = False
            t.updated_at = datetime.utcnow()

        # Set thread được chọn thành active
        thread.is_active = True
        thread.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(thread)

        return {
            "id": str(thread.id),
            "title": thread.title,
            "scope": thread.scope,
            "is_active": thread.is_active,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "course_id": str(thread.course_id),
            "lesson_id": str(thread.lesson_id),
        }


# =========================
# FASTAPI DEPENDENCY
# =========================


def get_tutor_chat_service(
    db: AsyncSession = Depends(get_session),
) -> TutorChatService:
    return TutorChatService(db=db)
