# app/services/lecturer/course_section_service.py
from fastapi import Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import Courses, CourseSections, User
from app.db.sesson import get_session
from app.schemas.course_sections import CreateCourseSection


class CourseSectionService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def create_section_async(self, schema: CreateCourseSection, lecturer: User):
        try:
            # 🔍 Kiểm tra khóa học có thuộc giảng viên này không
            course_lecturer = await self.db.scalar(
                select(Courses).where(
                    Courses.id == schema.course_id, Courses.instructor_id == lecturer.id
                )
            )
            if not course_lecturer:
                raise HTTPException(404, "Không tìm thấy khóa học thuộc giảng viên này")

            # 📚 Lấy chương có position cao nhất trong khóa học
            last_section = await self.db.scalar(
                select(CourseSections)
                .where(CourseSections.course_id == schema.course_id)
                .order_by(desc(CourseSections.position))
            )

            new_section = CourseSections(**schema.model_dump())
            new_section.position = (last_section.position + 1) if last_section else 0

            self.db.add(new_section)
            await self.db.commit()
            await self.db.refresh(new_section)
            return {"message": "Tạo chương học thành công", "section": new_section}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo chương học: {e}")
