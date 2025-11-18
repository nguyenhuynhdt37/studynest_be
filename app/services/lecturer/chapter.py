# app/services/lecturer/course_service.py
import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import EmbeddingService, get_embedding_service
from app.db.models.database import Courses, CourseSections
from app.db.sesson import get_session
from app.schemas.lecturer.chapter import (
    CreateCourseSection,
    ReorderSectionsSchema,
    UpdateCourseSection,
)
from app.services.shares.google_driver import (
    GoogleDriveAsyncService,
    get_google_drive_service,
)


class ChapterService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive: GoogleDriveAsyncService = Depends(get_google_drive_service),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db
        self.google_drive = google_drive
        self.embedding = embedding

    async def get_course_structure(self, course_id: uuid.UUID, lecturer_id: uuid.UUID):
        """Lấy danh sách chương và bài học theo khóa học (để hiển thị dạng cây)"""

        course = await self.db.get(Courses, course_id)
        if not course or course.instructor_id != lecturer_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        sections = await self.db.scalars(
            select(CourseSections)
            .options(selectinload(CourseSections.lessons))
            .where(CourseSections.course_id == course_id)
            .order_by(CourseSections.position)
        )
        data = []
        for sec in sections:
            lessons = sorted(sec.lessons, key=lambda l: l.position)
            data.append(
                {
                    "section_id": str(sec.id),
                    "section_title": sec.title,
                    "position": sec.position,
                    "lessons": [
                        {
                            "lesson_id": str(les.id),
                            "lesson_title": les.title,
                            "lesson_type": les.lesson_type,
                            "position": les.position,
                        }
                        for les in lessons
                    ],
                }
            )
        return {"course_id": course_id, "sections": data}

    async def update_section_async(
        self,
        course_section_id: uuid.UUID,
        schema: UpdateCourseSection,
        lecturer_id: uuid.UUID,
    ):
        try:
            # 🔍 Kiểm tra khóa học có thuộc giảng viên này không
            course_lecturer = await self.db.scalar(
                select(Courses)
                .join(CourseSections, CourseSections.course_id == Courses.id)
                .where(Courses.instructor_id == lecturer_id)
                .distinct()
                .limit(1)
            )
            if not course_lecturer:
                raise HTTPException(404, "Không tìm thấy khóa học thuộc giảng viên này")

            course_section: CourseSections | None = await self.db.get(
                CourseSections, course_section_id
            )
            if not course_section:
                raise HTTPException(404, "Không tìm thấy chương học")

            course_section.title = schema.title
            await self.db.commit()
            await self.db.refresh(course_section)
            return {
                "section_id": course_section.id,
                "section_title": course_section.title,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo chương học: {e}")

    async def create_section_async(
        self, course_id: uuid.UUID, schema: CreateCourseSection, lecturer_id: uuid.UUID
    ):
        try:
            # 🔍 Kiểm tra khóa học có thuộc giảng viên này không
            course_lecturer = await self.db.scalar(
                select(Courses).where(
                    Courses.id == course_id, Courses.instructor_id == lecturer_id
                )
            )
            if not course_lecturer:
                raise HTTPException(404, "Không tìm thấy khóa học thuộc giảng viên này")

            # 📚 Lấy chương có position cao nhất trong khóa học
            last_section = await self.db.scalar(
                select(CourseSections)
                .where(CourseSections.course_id == course_id)
                .order_by(desc(CourseSections.position))
            )

            new_section = CourseSections(**schema.model_dump(), course_id=course_id)
            new_section.position = (last_section.position + 1) if last_section else 0

            self.db.add(new_section)
            await self.db.commit()
            await self.db.refresh(new_section)
            return {
                "section_id": new_section.id,
                "section_title": new_section.title,
                "position": new_section.position,
                "lessons": [],
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo chương học: {e}")

    async def delete_section_async(
        self, course_section_id: uuid.UUID, lecturer_id: uuid.UUID
    ):
        try:
            # 🔍 Kiểm tra khóa học có thuộc giảng viên này không
            course_lecturer = await self.db.scalar(
                select(Courses)
                .join(CourseSections, CourseSections.course_id == Courses.id)
                .where(Courses.instructor_id == lecturer_id)
                .distinct()
                .limit(1)
            )
            if not course_lecturer:
                raise HTTPException(404, "Không tìm thấy khóa học thuộc giảng viên này")

            course_section: CourseSections | None = await self.db.get(
                CourseSections, course_section_id
            )
            if not course_section:
                raise HTTPException(404, "Không tìm thấy chương học")

            await self.db.delete(course_section)
            await self.db.commit()
            return {"detail": "Xóa chương học thành công"}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi xóa chương học: {e}")

    async def reorder_sections_async(
        self,
        course_id: uuid.UUID,
        schema: ReorderSectionsSchema,
        lecturer_id: uuid.UUID,
    ):
        """
        ✅ Sắp xếp lại thứ tự chương học trong khóa học.
        - Cập nhật order_index bắt đầu từ 0
        """
        # 🔍 Kiểm tra khóa học có thuộc giảng viên này không
        course_lecturer = await self.db.scalar(
            select(Courses).where(
                Courses.id == course_id, Courses.instructor_id == lecturer_id
            )
        )
        if not course_lecturer:
            raise HTTPException(404, "Không tìm thấy khóa học thuộc giảng viên này")

        # 1️⃣ Lấy danh sách section thuộc course
        result = await self.db.scalars(
            select(CourseSections.id).where(CourseSections.course_id == course_id)
        )
        valid_section_ids = {r for r in result}

        # 2️⃣ Kiểm tra tính hợp lệ
        for sid in schema.section_ids:
            if sid not in valid_section_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Section {sid} không thuộc course {course_id}",
                )

        # 3️⃣ Cập nhật order_index (0-based)
        for index, sid in enumerate(schema.section_ids):
            await self.db.execute(
                update(CourseSections)
                .where(CourseSections.id == sid)
                .values(position=index)
            )

        await self.db.commit()
        return {"detail": "Sắp xếp chương học thành công"}
