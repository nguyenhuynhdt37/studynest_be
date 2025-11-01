# app/services/lecturer/course_service.py
import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import EmbeddingService
from app.db.models.database import Courses, CourseSections
from app.db.sesson import get_session
from app.schemas.lecturer.chapter import CreateCourseSection
from app.services.shares.google_driver import GoogleDriveService


class ChapterService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive: GoogleDriveService = Depends(GoogleDriveService),
        embedding: EmbeddingService = Depends(EmbeddingService),
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

            new_section = CourseSections(**schema.model_dump())
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
