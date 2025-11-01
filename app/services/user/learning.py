import random
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.database import (
    CourseEnrollments,
    Courses,
    CourseSections,
    LessonActive,
    LessonProgress,
    LessonQuizzes,
    Lessons,
    LessonVideos,
    User,
)
from app.db.sesson import get_session


class LearningService:
    """Service quản lý học tập của người dùng."""

    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_course_enrolled_async(self, course_slug: str, user: User):
        try:
            # 1️⃣ Kiểm tra khóa học tồn tại
            course: Courses | None = await self.db.scalar(
                select(Courses).where(Courses.slug == course_slug)
            )
            if course is None:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            # 2️⃣ Kiểm tra người dùng đã đăng ký chưa
            enrolled = await self.db.scalar(
                select(CourseEnrollments)
                .where(CourseEnrollments.course_id == course.id)
                .where(CourseEnrollments.user_id == user.id)
            )
            if enrolled is None:
                raise HTTPException(
                    status_code=403, detail="Bạn chưa đăng ký khóa học này"
                )

            # 3️⃣ Trả dữ liệu khóa học
            return {
                "id": course.id,
                "title": course.title,
                "slug": course.slug,
                "subtitle": course.subtitle,
                "description": course.description,
                "level": course.level,
                "language": course.language,
                "thumbnail_url": course.thumbnail_url,
                "promo_video_url": course.promo_video_url,
                "is_published": course.is_published,
                "rating_avg": course.rating_avg,
                "rating_count": course.rating_count,
                "created_at": course.created_at,
                "updated_at": course.updated_at,
                "outcomes": course.outcomes,
                "requirements": course.requirements,
                "target_audience": course.target_audience,
                "views": course.views,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {e}")

    async def get_instructor_by_course_id_async(self, course_id: uuid.UUID, user: User):
        try:
            course: Courses | None = await self.db.get(Courses, course_id)
            if course is None:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            enrolled = await self.db.scalar(
                select(CourseEnrollments)
                .where(CourseEnrollments.course_id == course.id)
                .where(CourseEnrollments.user_id == user.id)
            )
            if enrolled is None:
                raise HTTPException(
                    status_code=403, detail="Bạn chưa đăng ký khóa học này"
                )

            instructor = await self.db.get(User, course.instructor_id)
            if instructor is None:
                raise HTTPException(status_code=404, detail="Giang vien khong ton tai")
            return {
                "id": instructor.id,
                "avatar": instructor.avatar,
                "conscious": instructor.conscious,
                "district": instructor.district,
                "citizenship_identity": instructor.citizenship_identity,
                "instructor_description": instructor.instructor_description,
                "facebook_url": instructor.facebook_url,
                "student_count": instructor.student_count,
                "rating_avg": instructor.rating_avg,
                "evaluated_count": instructor.evaluated_count,
                "course_count": instructor.course_count,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {e}")

    async def get_course_curriculum_async(
        self,
        course_id: uuid.UUID,
        user: User | None,
    ):
        try:
            # 0️⃣ Guard
            if user is None or getattr(user, "id", None) is None:
                raise HTTPException(status_code=401, detail="Unauthorized")

            # 1️⃣ Lấy khóa học
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            # 2️⃣ Kiểm tra đăng ký
            enrolled = await self.db.scalar(
                select(CourseEnrollments)
                .where(
                    CourseEnrollments.course_id == course.id,
                    CourseEnrollments.user_id == user.id,
                )
                .limit(1)
            )
            if not enrolled:
                raise HTTPException(
                    status_code=403, detail="Bạn chưa đăng ký khóa học này"
                )

            # 3️⃣ Sections + Lessons (+ Resources)
            stmt = (
                select(CourseSections)
                .where(CourseSections.course_id == course.id)
                .options(
                    selectinload(CourseSections.lessons).selectinload(
                        Lessons.lesson_resources
                    )
                )
                .order_by(CourseSections.position)
            )
            result = await self.db.execute(stmt)
            sections = [s for s in result.unique().scalars().all() if s is not None]

            # 4️⃣ Gom toàn bộ bài học
            all_lessons = []
            for s in sections:
                s_lessons = getattr(s, "lessons", []) or []
                all_lessons.extend([l for l in s_lessons if l is not None])

            all_lessons.sort(key=lambda l: (l.position or 0))
            if not all_lessons:
                return {
                    "course_id": str(course.id),
                    "title": course.title,
                    "is_lock_lesson": bool(course.is_lock_lesson),
                    "total_lessons": 0,
                    "completed_lessons": 0,
                    "total_duration": 0,
                    "progress_percent": 0.0,
                    "sections": [],
                }

            all_lesson_ids = [l.id for l in all_lessons]
            first_lesson_id = all_lessons[0].id

            # 5️⃣ Video info
            video_result = await self.db.execute(
                select(
                    LessonVideos.lesson_id,
                    LessonVideos.duration,
                    LessonVideos.file_id,
                    LessonVideos.video_url,
                ).where(LessonVideos.lesson_id.in_(all_lesson_ids))
            )
            video_map = {v.lesson_id: v for v in video_result}

            # 6️⃣ Progress
            is_lock_enabled = bool(course.is_lock_lesson)
            progress_map: dict[uuid.UUID, bool] = {}
            created_progress = False

            prog_result = await self.db.execute(
                select(
                    LessonProgress.lesson_id,
                    LessonProgress.is_completed,
                ).where(
                    LessonProgress.user_id == user.id,
                    LessonProgress.course_id == course.id,
                    LessonProgress.lesson_id.in_(all_lesson_ids),
                )
            )
            rows = prog_result.all()

            if not rows:
                self.db.add(
                    LessonProgress(
                        user_id=user.id,
                        course_id=course.id,
                        lesson_id=first_lesson_id,
                        is_completed=False,
                    )
                )
                await self.db.flush()
                created_progress = True
                progress_map[first_lesson_id] = False
            else:
                progress_map = {r.lesson_id: r.is_completed for r in rows}

            # 7️⃣ Active lesson
            existing_active = await self.db.scalar(
                select(LessonActive)
                .where(
                    LessonActive.user_id == user.id,
                    LessonActive.course_id == course.id,
                )
                .limit(1)
            )
            created_active = False
            if existing_active is None:
                self.db.add(
                    LessonActive(
                        user_id=user.id,
                        course_id=course.id,
                        lesson_id=first_lesson_id,
                        activated_at=datetime.utcnow(),
                    )
                )
                await self.db.flush()
                created_active = True

            # 8️⃣ Tính khóa/mở
            locked_ids: set[uuid.UUID] = set()
            if is_lock_enabled:
                gating_sequence = [l for l in all_lessons if not l.is_preview]
                completed_ids = {lid for lid, done in progress_map.items() if done}

                for idx, l in enumerate(gating_sequence):
                    if l.id == first_lesson_id:
                        continue
                    prev_lessons = gating_sequence[:idx]
                    if any(prev.id not in completed_ids for prev in prev_lessons):
                        locked_ids.add(l.id)

                for l in gating_sequence:
                    if l.id not in progress_map and l.id != first_lesson_id:
                        locked_ids.add(l.id)

            # 9️⃣ Build curriculum + thống kê
            curriculum = []
            total_course_lessons = 0
            total_course_completed = 0
            total_course_duration = 0.0

            for section in sections:
                lessons = getattr(section, "lessons", []) or []
                lessons_sorted = sorted(
                    [l for l in lessons if l is not None],
                    key=lambda l: (l.position or 0),
                )

                section_total = len(lessons_sorted)
                section_completed = 0
                section_duration = 0.0
                lessons_data = []

                for lesson in lessons_sorted:
                    video_info = video_map.get(lesson.id)
                    is_completed = progress_map.get(lesson.id, False)

                    if not is_lock_enabled:
                        is_locked = False
                    elif lesson.is_preview or lesson.id == first_lesson_id:
                        is_locked = False
                    else:
                        is_locked = lesson.id in locked_ids

                    if is_completed:
                        section_completed += 1
                    if video_info and video_info.duration:
                        section_duration += float(video_info.duration)

                    resources = getattr(lesson, "lesson_resources", []) or []
                    lessons_data.append(
                        {
                            "id": str(lesson.id),
                            "title": lesson.title,
                            "lesson_type": lesson.lesson_type,
                            "is_preview": lesson.is_preview,
                            "position": lesson.position,
                            "is_completed": is_completed,
                            "is_locked": is_locked,
                            "duration": (
                                float(video_info.duration)
                                if video_info and video_info.duration
                                else None
                            ),
                            "file_id": (
                                str(video_info.file_id)
                                if video_info and video_info.file_id
                                else None
                            ),
                            "resources": resources or [],
                        }
                    )

                total_course_lessons += section_total
                total_course_completed += section_completed
                total_course_duration += section_duration

                curriculum.append(
                    {
                        "id": str(section.id),
                        "title": section.title,
                        "position": section.position,
                        "total_lessons": section_total,
                        "completed_lessons": section_completed,
                        "total_duration": round(section_duration, 2),
                        "lessons": lessons_data,
                    }
                )

            # 🔟 Commit khi có thay đổi
            if created_progress or created_active:
                await self.db.commit()

            # 🧮 Tính % hoàn thành khóa học
            progress_percent = (
                (total_course_completed / total_course_lessons) * 100
                if total_course_lessons > 0
                else 0.0
            )

            return {
                "course_id": str(course.id),
                "title": course.title,
                "is_lock_lesson": is_lock_enabled,
                "total_lessons": total_course_lessons,
                "completed_lessons": total_course_completed,
                "total_duration": round(total_course_duration, 2),
                "progress_percent": round(progress_percent, 2),
                "sections": curriculum,
            }

        except HTTPException:
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi cơ sở dữ liệu: {e}")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi server: {e}")

    async def get_type_and_lesson_id_by_course_id_active(
        self, course_id: uuid.UUID, user: User
    ):
        try:
            if user is None or getattr(user, "id", None) is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
                )

                # 1️⃣ Khóa học
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

                # 2️⃣ Đăng ký
            enrolled = await self.db.scalar(
                select(CourseEnrollments)
                .where(
                    CourseEnrollments.course_id == course.id,
                    CourseEnrollments.user_id == user.id,
                )
                .limit(1)
            )
            if not enrolled:
                raise HTTPException(
                    status_code=403, detail="Bạn chưa đăng ký khóa học này"
                )
            lesson_active: LessonActive | None = await self.db.scalar(
                select(LessonActive).where(
                    LessonActive.user_id == user.id, LessonActive.course_id == course_id
                )
            )
            if lesson_active is None:
                raise HTTPException(404, "Bài học này chưa được active")
            lesson_type = await self.db.scalar(
                select(Lessons.lesson_type).where(Lessons.id == lesson_active.lesson_id)
            )
            if not lesson_type:
                raise HTTPException(404, "khong tim thay lesson type")
            return [lesson_type, lesson_active.lesson_id]
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi server: {e}")

    async def get_prev_next_lesson_async(
        self,
        lesson_id: uuid.UUID,
        user: User | None,
    ):
        """
        ✅ Lấy bài học trước và sau (smart navigation):
        - Duyệt theo section.position + lesson.position
        - Nhảy qua section trống
        - Tôn trọng rule khóa học (is_lock_lesson)
        """

        try:
            # 1️⃣ Kiểm tra user
            if user is None or getattr(user, "id", None) is None:
                raise HTTPException(401, "Unauthorized")

            # 2️⃣ Lấy bài học + khóa học
            lesson: Lessons | None = await self.db.scalar(
                select(Lessons)
                .options(
                    selectinload(Lessons.section).selectinload(CourseSections.course)
                )
                .where(Lessons.id == lesson_id)
            )
            if not lesson:
                raise HTTPException(404, "Không tìm thấy bài học")

            course = (
                lesson.section.course
                if lesson.section and lesson.section.course
                else None
            )
            if not course:
                raise HTTPException(404, "Không tìm thấy khóa học")

            # 3️⃣ Lấy tất cả section + lesson để tạo danh sách tuyến tính
            stmt = (
                select(CourseSections)
                .where(CourseSections.course_id == course.id)
                .options(selectinload(CourseSections.lessons))
                .order_by(CourseSections.position)
            )
            result = await self.db.execute(stmt)
            sections = result.scalars().all()

            # Gom tất cả bài học (section.position → lesson.position)
            all_lessons: list[Lessons] = []
            for sec in sections:
                lessons = sorted(
                    [l for l in (sec.lessons or []) if l is not None],
                    key=lambda l: (l.position or 0),
                )
                all_lessons.extend(lessons)

            if not all_lessons:
                raise HTTPException(404, "Khóa học chưa có bài học nào")

            # 4️⃣ Tìm index hiện tại
            lesson_ids = [l.id for l in all_lessons]
            try:
                current_index = lesson_ids.index(lesson.id)
            except ValueError:
                raise HTTPException(404, "Bài học không thuộc khóa học này")

            # Tìm bài trước & sau (bỏ qua section trống)
            prev_lesson = None
            next_lesson = None

            # Lùi lại cho tới khi gặp bài trước hợp lệ
            for i in range(current_index - 1, -1, -1):
                if all_lessons[i]:
                    prev_lesson = all_lessons[i]
                    break

            # Tiến tới bài sau hợp lệ
            for i in range(current_index + 1, len(all_lessons)):
                if all_lessons[i]:
                    next_lesson = all_lessons[i]
                    break

            # 5️⃣ Lấy progress để xác định đã hoàn thành
            prog_result = await self.db.execute(
                select(LessonProgress.lesson_id, LessonProgress.is_completed).where(
                    LessonProgress.user_id == user.id,
                    LessonProgress.course_id == course.id,
                )
            )
            progress_map = {r.lesson_id: r.is_completed for r in prog_result}
            completed_ids = {lid for lid, done in progress_map.items() if done}

            # 6️⃣ Tính logic khóa
            is_lock_enabled = bool(course.is_lock_lesson)

            def is_locked(target: Lessons | None):
                if target is None:
                    return True
                if not is_lock_enabled:
                    return False
                if target.is_preview:
                    return False
                idx = lesson_ids.index(target.id)
                # nếu có bất kỳ bài trước chưa hoàn thành -> khóa
                prev_lessons = all_lessons[:idx]
                return any(p.id not in completed_ids for p in prev_lessons)

            can_prev = prev_lesson is not None and not is_locked(prev_lesson)
            can_next = next_lesson is not None and not is_locked(next_lesson)

            return {
                "current_lesson_id": str(lesson.id),
                "prev_lesson_id": str(prev_lesson.id) if prev_lesson else None,
                "next_lesson_id": str(next_lesson.id) if next_lesson else None,
                "can_prev": can_prev,
                "can_next": can_next,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi server: {e}")

    async def get_lesson_video_async(self, lesson_id, user):
        """
        ✅ Lấy toàn bộ dữ liệu bài học:
        - Video / Tài nguyên / Quiz (với options)
        - Trạng thái đã học, khóa/mở
        - Random thứ tự đáp án mà không mất feedback hoặc is_correct
        """

        try:
            # 1️⃣ Lấy bài học đầy đủ thông tin
            lesson = await self.db.scalar(
                select(Lessons)
                .options(
                    selectinload(Lessons.lesson_videos),
                    selectinload(Lessons.lesson_resources),
                    selectinload(Lessons.lesson_quizzes).selectinload(
                        LessonQuizzes.lesson_quiz_options
                    ),
                    selectinload(Lessons.section).selectinload(CourseSections.course),
                )
                .where(Lessons.id == lesson_id)
            )

            if not lesson:
                raise HTTPException(404, "Không tìm thấy bài học")

            # 2️⃣ Lấy tiến độ học
            progress = await self.db.scalar(
                select(LessonProgress).where(
                    LessonProgress.lesson_id == lesson_id,
                    LessonProgress.user_id == user.id,
                )
            )

            is_completed = bool(progress and progress.is_completed)
            is_locked = bool(getattr(lesson.section.course, "is_lock_lesson", False))

            # 3️⃣ Random đáp án cho từng quiz
            quizzes = []
            for q in lesson.lesson_quizzes or []:
                options = q.lesson_quiz_options or []
                shuffled = list(options)
                random.shuffle(shuffled)

                formatted_opts = [
                    {
                        "id": str(opt.id),
                        "text": opt.text_,
                        "is_correct": bool(opt.is_correct),
                        "feedback": opt.feedback,
                        "position": opt.position,
                    }
                    for opt in shuffled
                ]

                quizzes.append(
                    {
                        "id": str(q.id),
                        "question": q.question,
                        "difficulty_level": q.difficulty_level,
                        "explanation": q.explanation,
                        "options": formatted_opts,
                    }
                )

            # 4️⃣ Trả dữ liệu hoàn chỉnh cho frontend
            return {
                "id": str(lesson.id),
                "title": lesson.title,
                "lesson_type": lesson.lesson_type,
                "duration": (
                    lesson.lesson_videos.duration if lesson.lesson_videos else 0
                ),
                "file_id": (
                    lesson.lesson_videos.file_id if lesson.lesson_videos else None
                ),
                "resources": lesson.lesson_resources,
                "quizzes": quizzes,
                "is_completed": is_completed,
                "is_locked": is_locked,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi server khi lấy bài học: {e}")

    async def get_lesson_quiz_async(self, lesson_id, user):
        """
        ✅ Lấy toàn bộ dữ liệu bài học:
        - Video / Tài nguyên / Quiz (với options)
        - Trạng thái đã học, khóa/mở
        - Random thứ tự đáp án mà không mất feedback hoặc is_correct
        """

        try:
            # 1️⃣ Lấy bài học đầy đủ thông tin
            lesson = await self.db.scalar(
                select(Lessons)
                .options(
                    selectinload(Lessons.lesson_videos),
                    selectinload(Lessons.lesson_quizzes).selectinload(
                        LessonQuizzes.lesson_quiz_options
                    ),
                    selectinload(Lessons.section).selectinload(CourseSections.course),
                )
                .where(Lessons.id == lesson_id)
            )

            if not lesson:
                raise HTTPException(404, "Không tìm thấy bài học")

            # 2️⃣ Lấy tiến độ học
            progress = await self.db.scalar(
                select(LessonProgress).where(
                    LessonProgress.lesson_id == lesson_id,
                    LessonProgress.user_id == user.id,
                )
            )

            is_completed = bool(progress and progress.is_completed)
            is_locked = bool(getattr(lesson.section.course, "is_lock_lesson", False))

            quizzes = []
            for q in lesson.lesson_quizzes or []:
                options = q.lesson_quiz_options or []
                shuffled = list(options)
                random.shuffle(shuffled)

                formatted_opts = [
                    {
                        "id": str(opt.id),
                        "text": opt.text_,
                        "is_correct": bool(opt.is_correct),
                        "feedback": opt.feedback,
                        "position": opt.position,
                    }
                    for opt in shuffled
                ]

                quizzes.append(
                    {
                        "id": str(q.id),
                        "question": q.question,
                        "difficulty_level": q.difficulty_level,
                        "explanation": q.explanation,
                        "options": formatted_opts,
                    }
                )

            # 4️⃣ Trả dữ liệu hoàn chỉnh cho frontend
            return {
                "id": str(lesson.id),
                "title": lesson.title,
                "lesson_type": lesson.lesson_type,
                "quizzes": quizzes,
                "is_completed": is_completed,
                "is_locked": is_locked,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi server khi lấy bài học: {e}")

    async def set_active_lesson_async(
        self, course_id: uuid.UUID, lesson_id: uuid.UUID, user: User
    ):
        try:

            if user is None or getattr(user, "id", None) is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
                )

                # 1️⃣ Khóa học
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

                # 2️⃣ Đăng ký
            enrolled = await self.db.scalar(
                select(CourseEnrollments)
                .where(
                    CourseEnrollments.course_id == course.id,
                    CourseEnrollments.user_id == user.id,
                )
                .limit(1)
            )
            if not enrolled:
                raise HTTPException(
                    status_code=403, detail="Bạn chưa đăng ký khóa học này"
                )

            lesson_active: LessonActive | None = await self.db.scalar(
                select(LessonActive).where(
                    LessonActive.user_id == user.id, LessonActive.course_id == course_id
                )
            )

            if lesson_active is None:
                lesson_active = LessonActive(
                    course_id=course_id, lesson_id=lesson_id, user_id=user.id
                )
                self.db.add(lesson_active)

            else:
                lesson_active.lesson_id = lesson_id
                lesson_active.activated_at = datetime.utcnow()
                await self.db.commit()
            await self.db.commit()
            await self.db.refresh(lesson_active)

            return lesson_active

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi server {e}")

    async def get_next_lesson_in_course_async(
        self,
        current_lesson_id: uuid.UUID,
        user: Optional[User] = None,
        strict: bool = True,
    ) -> dict[str, Optional[Any]] | None:
        """
        🔜 Tìm bài học kế tiếp trong khóa học.
        - Nếu strict = True = > chỉ trả bài kế khi user đủ điều kiện(đã hoàn thành bài hiện tại).
        - Nếu strict = False = > bỏ qua kiểm tra(dùng trong mark completed).
        - Nếu khóa học bật is_lock_lesson = > các bài chưa có progress đều bị coi là "locked".
        """

        current_lesson = await self.db.get(Lessons, current_lesson_id)
        if not current_lesson:
            return None

        course = await self.db.get(Courses, current_lesson.course_id)
        if not course:
            return None

        current_section_id = current_lesson.section_id
        course_id = course.id

        sections = (
            (
                await self.db.execute(
                    select(CourseSections)
                    .where(CourseSections.course_id == course_id)
                    .order_by(CourseSections.position)
                )
            )
            .scalars()
            .all()
        )

        lessons = (
            (
                await self.db.execute(
                    select(Lessons)
                    .where(Lessons.course_id == course_id)
                    .order_by(Lessons.section_id, Lessons.position)
                )
            )
            .scalars()
            .all()
        )

        lessons_by_section: dict[Optional[uuid.UUID], list[Lessons]] = {}
        for l in lessons:
            lessons_by_section.setdefault(l.section_id, []).append(l)

        next_lesson: Optional[Lessons] = None
        current_section_lessons = lessons_by_section.get(current_section_id, [])

        for idx, l in enumerate(current_section_lessons):
            if l.id == current_lesson_id and idx + 1 < len(current_section_lessons):
                next_lesson = current_section_lessons[idx + 1]
                break

        if not next_lesson:
            found = False
            for sec in sections:
                if found:
                    next_sec_lessons = lessons_by_section.get(sec.id, [])
                    if next_sec_lessons:
                        next_lesson = next_sec_lessons[0]
                        break
                if sec.id == current_section_id:
                    found = True

        if not next_lesson:
            return {"next_lesson_id": None, "can_next": False}
        can_next = True

        if course.is_lock_lesson and user:

            if strict:
                completed = await self.db.scalar(
                    select(LessonProgress.is_completed).where(
                        LessonProgress.user_id == user.id,
                        LessonProgress.lesson_id == current_lesson_id,
                        LessonProgress.course_id == course_id,
                    )
                )
                if not completed:
                    return {"next_lesson_id": next_lesson.id, "can_next": False}

            # Nếu bài kế tiếp chưa có progress record → coi như bị khóa
            next_prog = await self.db.scalar(
                select(LessonProgress).where(
                    LessonProgress.user_id == user.id,
                    LessonProgress.course_id == course_id,
                    LessonProgress.lesson_id == next_lesson.id,
                )
            )
            if next_prog is None:
                can_next = False

        return {"next_lesson_id": next_lesson.id, "can_next": can_next}

    async def get_previous_lesson_in_course_async(
        self,
        current_lesson_id: uuid.UUID,
        user,
    ) -> dict:
        """
        🔙 Trả về bài học TRƯỚC đó trong khóa học(smart version)
        - Dựa vào section.position + lesson.position
        - Nếu hết bài trong section = > sang section trước(bài cuối cùng)
        - Nếu khóa học bật khóa tuần tự = > kiểm tra quyền truy cập
        """

        # 1️⃣ Lấy bài học hiện tại
        current_lesson = await self.db.get(Lessons, current_lesson_id)
        if not current_lesson:
            raise HTTPException(404, "Không tìm thấy bài học hiện tại")

        course_id = current_lesson.course_id
        section_id = current_lesson.section_id

        # 2️⃣ Lấy khóa học
        course = await self.db.get(Courses, course_id)
        if not course:
            raise HTTPException(404, "Không tìm thấy khóa học")

        is_lock_enabled = bool(course.is_lock_lesson)

        # 3️⃣ Lấy danh sách section theo thứ tự
        sections = (
            (
                await self.db.execute(
                    select(CourseSections)
                    .where(CourseSections.course_id == course_id)
                    .order_by(CourseSections.position)
                )
            )
            .scalars()
            .all()
        )

        # 4️⃣ Gom danh sách bài học theo section
        lessons = (
            (
                await self.db.execute(
                    select(Lessons)
                    .where(Lessons.course_id == course_id)
                    .order_by(Lessons.section_id, Lessons.position)
                )
            )
            .scalars()
            .all()
        )

        lessons_by_section: dict[Optional[uuid.UUID], list[Lessons]] = {}
        for l in lessons:
            lessons_by_section.setdefault(l.section_id, []).append(l)

        # 5️⃣ Tìm bài học trước trong cùng section
        prev_lesson = None
        current_lessons = lessons_by_section.get(section_id, [])
        for idx, l in enumerate(current_lessons):
            if l.id == current_lesson_id and idx > 0:
                prev_lesson = current_lessons[idx - 1]
                break

        # 6️⃣ Nếu không còn bài trong section → sang section trước
        if not prev_lesson:
            for idx, sec in enumerate(sections):
                if sec.id == section_id and idx > 0:
                    for prev_sec in reversed(sections[:idx]):
                        prev_lessons = lessons_by_section.get(prev_sec.id, [])
                        if prev_lessons:
                            prev_lesson = prev_lessons[-1]
                            break
                    break

        # 7️⃣ Không có bài học trước đó
        if not prev_lesson:
            return {"prev_lesson_id": None, "can_prev": False}

        # 8️⃣ Kiểm tra khóa tuần tự (nếu bật)
        can_prev = True
        if is_lock_enabled:
            prog_result = await self.db.execute(
                select(LessonProgress.lesson_id, LessonProgress.is_completed).where(
                    LessonProgress.user_id == user.id,
                    LessonProgress.course_id == course.id,
                )
            )
            progress_map = {r.lesson_id: r.is_completed for r in prog_result}
            completed_ids = {lid for lid, done in progress_map.items() if done}

            # Bài trước chỉ mở khi các bài trước nó đều hoàn thành
            all_lessons_linear = [
                l for sec in sections for l in lessons_by_section.get(sec.id, [])
            ]
            idx_prev = all_lessons_linear.index(prev_lesson)
            required = all_lessons_linear[:idx_prev]

            if any(r.id not in completed_ids for r in required):
                can_prev = False

        # ✅ Kết quả cuối
        return {
            "prev_lesson_id": str(prev_lesson.id),
            "can_prev": can_prev,
        }

    async def mark_lesson_completed_async(
        self,
        lesson_id: uuid.UUID,
        user: User,
    ):
        """
        ✅ Đánh dấu hoàn thành 1 bài học:
        - Đánh completed cho bài hiện tại.
        - Mở khóa bài tiếp theo(nếu chưa có record trong progress).
        - Nếu tiến độ >= 85 % → mở khóa toàn bộ bài còn lại.
        """

        try:
            # 1️⃣ Kiểm tra bài học hiện tại
            lesson = await self.db.get(Lessons, lesson_id)
            if not lesson:
                raise HTTPException(404, "Bài học không tồn tại")

            course_id = lesson.course_id
            now = func.now()

            # 2️⃣ Kiểm tra progress hiện tại
            progress = await self.db.scalar(
                select(LessonProgress).where(
                    LessonProgress.user_id == user.id,
                    LessonProgress.course_id == course_id,
                    LessonProgress.lesson_id == lesson_id,
                )
            )

            if progress and progress.is_completed:
                return {"status": "noop", "message": "Bài học đã hoàn thành"}

            # ✅ Cập nhật hoặc tạo mới progress
            if progress:
                progress.is_completed = True
                progress.completed_at = now
                progress.updated_at = now
            else:
                self.db.add(
                    LessonProgress(
                        user_id=user.id,
                        course_id=course_id,
                        lesson_id=lesson_id,
                        is_completed=True,
                        completed_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )

            unlocked_lessons = []
            is_course_unlocked = False
            next_suggestion = None

            # 3️⃣ Lấy bài học kế tiếp (hàm trả về dict)
            next_info = await self.get_next_lesson_in_course_async(
                lesson_id, user, strict=False
            )
            if next_info and next_info.get("next_lesson_id"):
                next_lesson_id = next_info["next_lesson_id"]

                # Lấy object thật từ DB
                next_lesson_obj = await self.db.get(Lessons, next_lesson_id)
                if next_lesson_obj:
                    next_progress = await self.db.scalar(
                        select(LessonProgress).where(
                            LessonProgress.user_id == user.id,
                            LessonProgress.course_id == course_id,
                            LessonProgress.lesson_id == next_lesson_id,
                        )
                    )

                    # Nếu chưa có progress cho bài kế tiếp → tạo record mới
                    if not next_progress:
                        self.db.add(
                            LessonProgress(
                                user_id=user.id,
                                course_id=course_id,
                                lesson_id=next_lesson_id,
                                is_completed=False,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                        unlocked_lessons.append(str(next_lesson_id))

                    # Gợi ý bài học kế tiếp
                    next_suggestion = {
                        "id": str(next_lesson_obj.id),
                        "title": next_lesson_obj.title,
                        "section_id": str(next_lesson_obj.section_id),
                        "is_preview": bool(next_lesson_obj.is_preview),
                    }

            # 4️⃣ Tính tiến độ toàn khóa
            total_lessons = await self.db.scalar(
                select(func.count(Lessons.id)).where(Lessons.course_id == course_id)
            )
            completed_lessons = await self.db.scalar(
                select(func.count(LessonProgress.id)).where(
                    LessonProgress.course_id == course_id,
                    LessonProgress.user_id == user.id,
                    LessonProgress.is_completed.is_(True),
                )
            )

            completion_rate = completed_lessons / total_lessons if total_lessons else 0

            # 5️⃣ Nếu >=85% → mở khóa tất cả bài còn lại
            if completion_rate >= 0.85:
                is_course_unlocked = True
                lessons_result = await self.db.execute(
                    select(Lessons.id).where(Lessons.course_id == course_id)
                )
                all_lesson_ids = [r.id for r in lessons_result]

                existing_result = await self.db.execute(
                    select(LessonProgress.lesson_id).where(
                        LessonProgress.course_id == course_id,
                        LessonProgress.user_id == user.id,
                    )
                )
                existing_ids = {r.lesson_id for r in existing_result}

                for lid in all_lesson_ids:
                    if lid not in existing_ids:
                        self.db.add(
                            LessonProgress(
                                user_id=user.id,
                                course_id=course_id,
                                lesson_id=lid,
                                is_completed=False,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                        unlocked_lessons.append(str(lid))

            # ✅ Commit thay đổi
            await self.db.commit()

            # 6️⃣ Trả kết quả
            return {
                "status": "success",
                "lesson_id": str(lesson_id),
                "course_id": str(course_id),
                "completion_percent": round(completion_rate * 100, 2),
                "is_course_unlocked": is_course_unlocked,
                "unlocked_lessons": unlocked_lessons,
                "next_lesson_suggestion": next_suggestion,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi server khi hoàn thành bài học: {e}")
