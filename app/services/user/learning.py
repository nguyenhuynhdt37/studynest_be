import random
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import asc, delete, desc, exists, func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import get_embedding_service
from app.core.ws_manager import ws_manager
from app.db.models.database import (
    CourseEnrollments,
    Courses,
    CourseSections,
    LessonActive,
    LessonCodeFiles,
    LessonCodes,
    LessonCommentReactions,
    LessonComments,
    LessonNotes,
    LessonProgress,
    LessonQuizzes,
    Lessons,
    LessonVideos,
    SupportedLanguages,
    User,
)
from app.db.sesson import AsyncSessionLocal, get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import to_utc_naive
from app.schemas.lecturer.lesson import LessonCodeSaveFile, LessonCodeUserTest
from app.schemas.user.learning import (
    CreateLessonComment,
    CreateLessonNote,
    UpdateLessonComment,
    UpdateLessonNote,
)
from app.services.shares.code_runner import PistonService


class LearningService:
    """Service quản lý học tập của người dùng."""

    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        piston: PistonService = Depends(PistonService),
    ):
        self.db = db
        self.piston = piston

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
                "fullname": instructor.fullname,
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
                        activated_at=get_now(),
                    )
                )
                await self.db.flush()
                created_active = True

            # 8️⃣ Tính khóa/mở
            locked_ids: set[uuid.UUID] = set()
            if is_lock_enabled:
                gating_sequence = [l for l in all_lessons if not l.is_preview]
                existing_progress_ids = set(progress_map.keys())

                locked_ids.clear()

                for lesson in gating_sequence:
                    # Bỏ qua bài đầu tiên
                    if lesson.id == first_lesson_id:
                        continue

                    # ❗Chỉ khóa nếu chưa từng có trong progress_map (tức là user chưa bao giờ học)
                    if lesson.id not in existing_progress_ids:
                        locked_ids.add(lesson.id)

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
                "description": lesson.description,
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
                "description": lesson.description,
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
                lesson_active.activated_at = get_now()
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

    async def get_code_language_by_language_id_async(self, language_id: uuid.UUID):
        """
        Lấy code template theo ngôn ngữ
        """
        try:
            code_template = await self.db.get(SupportedLanguages, language_id)
            if not code_template:
                raise HTTPException(404, "Không tìm thấy template cho ngôn ngữ này")
            if not code_template.is_active:
                raise HTTPException(404, "Template cho ngôn ngữ này đang trống")
            return {
                "name": code_template.name,
                "version": code_template.version,
                "aliases": code_template.aliases,
                "runtime": code_template.runtime,
                "last_sync": code_template.last_sync,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi server khi lấy template: {e}")

    async def get_lesson_code_async(self, lesson_id: str, user):
        """
        ✅ Lấy toàn bộ dữ liệu lesson dạng code:
        - Một lesson có nhiều bài code (LessonCodes)
        - Mỗi bài code có nhiều file + test case
        - Nếu user chưa có code riêng, lấy starter làm mặc định
        - Test case ẩn thì giấu input/output
        - Trả về trạng thái is_pass chính xác (theo user, lesson_code_id)
        """

        try:
            # 1️⃣ Lấy lesson kèm code + testcases + file
            lesson = await self.db.scalar(
                select(Lessons)
                .options(
                    selectinload(Lessons.lesson_codes).selectinload(
                        LessonCodes.language
                    ),
                    selectinload(Lessons.lesson_codes).selectinload(
                        LessonCodes.lesson_code_files
                    ),
                    selectinload(Lessons.lesson_codes).selectinload(
                        LessonCodes.lesson_code_testcases
                    ),
                    selectinload(Lessons.section).selectinload(CourseSections.course),
                )
                .where(Lessons.id == lesson_id)
            )

            if not lesson:
                raise HTTPException(404, "Không tìm thấy bài học")

            section = lesson.section
            course = getattr(section, "course", None)

            # 2️⃣ Tiến độ học
            progress = await self.db.scalar(
                select(LessonProgress).where(
                    LessonProgress.lesson_id == lesson_id,
                    LessonProgress.user_id == user.id,
                )
            )
            is_completed = bool(progress and progress.is_completed)
            is_locked = bool(getattr(course, "is_lock_lesson", False))

            # 3️⃣ Duyệt qua từng bài code
            codes_data = []
            for code in lesson.lesson_codes or []:
                lang = code.language
                language_info = {
                    "id": str(lang.id) if lang else None,
                    "name": lang.name if lang else None,
                    "version": lang.version if lang else None,
                    "runtime": lang.runtime if lang else None,
                }

                all_files = code.lesson_code_files or []
                user_files = [
                    f
                    for f in all_files
                    if f.role == "user"
                    and f.user_id == user.id
                    and f.lesson_code_id == code.id  # ✅ bắt buộc trùng lesson_code_id
                ]
                starter_files = [
                    f
                    for f in all_files
                    if f.role == "starter" and f.lesson_code_id == code.id
                ]

                active_files = user_files if user_files else starter_files

                def serialize_file(f):
                    return {
                        "id": str(f.id),
                        "filename": f.filename,
                        "content": f.content,
                        "role": f.role,
                        "is_main": bool(f.is_main),
                        "is_pass": bool(getattr(f, "is_pass", False)),
                    }

                files_user_or_starter = [serialize_file(f) for f in active_files]

                # ✅ Tính trạng thái pass chính xác (phải cùng user & lesson_code_id)
                user_code_files = [
                    f
                    for f in all_files
                    if f.role == "user"
                    and f.user_id == user.id
                    and f.lesson_code_id == code.id
                ]
                is_pass = len(user_code_files) > 0 and all(
                    getattr(f, "is_pass", False) for f in user_code_files
                )

                # --- Testcases ---
                testcase_items = []
                for t in code.lesson_code_testcases or []:
                    is_hidden = bool(t.is_sample) or (
                        getattr(t, "is_active", True) is False
                    )
                    testcase_items.append(
                        {
                            "id": str(t.id),
                            "input": None if is_hidden else (t.input or ""),
                            "expected_output": (
                                None if is_hidden else (t.expected_output or "")
                            ),
                            "is_sample": bool(t.is_sample),
                            "order_index": t.order_index,
                            "hidden": is_hidden,
                        }
                    )

                testcase_items.sort(key=lambda x: x["order_index"])

                codes_data.append(
                    {
                        "id": str(code.id),
                        "title": code.title,
                        "description": code.description,
                        "difficulty": code.difficulty,
                        "time_limit": code.time_limit,
                        "memory_limit": code.memory_limit,
                        "language": language_info,
                        "files": files_user_or_starter,
                        "testcases": testcase_items,
                        "is_pass": is_pass,  # ✅ user-specific pass flag
                    }
                )

            # 4️⃣ Kết quả
            return {
                "id": str(lesson.id),
                "title": lesson.title,
                "lesson_type": lesson.lesson_type,
                "description": lesson.description,
                "is_completed": is_completed,
                "is_locked": is_locked,
                "codes": codes_data,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi server khi lấy bài học code: {e}")

    async def save_single_user_code_async(
        self, lesson_code_id: uuid.UUID, user, file_obj: LessonCodeSaveFile
    ):
        """
        ✅ Lưu một file duy nhất khi user onLeave / blur khỏi file editor.
        - Nếu đã có: update content
        - Nếu chưa có: insert bản ghi mới
        """

        try:
            # 1️⃣ Kiểm tra bài code tồn tại
            code = await self.db.scalar(
                select(LessonCodes)
                .where(LessonCodes.id == lesson_code_id)
                .options(selectinload(LessonCodes.lesson_code_files))
            )
            if not code:
                raise HTTPException(404, "Không tìm thấy bài code")

            filename = file_obj.filename
            content = file_obj.content
            is_main = file_obj.is_main

            # 2️⃣ Kiểm tra file của user đã tồn tại chưa
            existing = await self.db.scalar(
                select(LessonCodeFiles).where(
                    LessonCodeFiles.lesson_code_id == code.id,
                    LessonCodeFiles.filename == filename,
                    LessonCodeFiles.user_id == user.id,
                    LessonCodeFiles.role == "user",
                )
            )

            if existing:
                # update nội dung
                await self.db.execute(
                    update(LessonCodeFiles)
                    .where(LessonCodeFiles.id == existing.id)
                    .values(
                        content=content,
                        is_main=is_main,
                        is_pass=False,
                        updated_at=await to_utc_naive(get_now()),
                    )
                )
                message = f"Đã cập nhật file '{filename}'"
            else:
                # insert mới
                await self.db.execute(
                    insert(LessonCodeFiles).values(
                        lesson_code_id=code.id,
                        filename=filename,
                        content=content,
                        role="user",
                        user_id=user.id,
                        is_main=is_main,
                        is_pass=False,
                        created_at=await to_utc_naive(get_now()),
                        updated_at=await to_utc_naive(get_now()),
                    )
                )
                message = f"Đã tạo mới file '{filename}'"

            await self.db.commit()
            return {"status": "ok", "message": message, "filename": filename}

        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi DB khi lưu code: {e}")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi server khi lưu code: {e}")

    async def test_user_code_async(
        self, payload: LessonCodeUserTest, user: User, lesson_code_id: uuid.UUID
    ):
        """
        ✅ Test code người dùng:
        - Lấy testcases từ DB → chạy từng cái
        - So sánh output, kiểm tra thời gian / bộ nhớ
        - Nếu pass toàn bộ → lưu file user + đánh dấu is_pass=True
        - Dùng ORM + await to_utc_naive(get_now())
        """

        try:
            # 1️⃣ Ngôn ngữ
            lang = await self.db.scalar(
                select(SupportedLanguages).where(
                    SupportedLanguages.id == payload.language_id
                )
            )
            if not lang:
                raise HTTPException(400, "🚫 Ngôn ngữ không hợp lệ")

            # 2️⃣ Lấy bài code + testcases
            lesson_code = await self.db.scalar(
                select(LessonCodes)
                .options(selectinload(LessonCodes.lesson_code_testcases))
                .where(LessonCodes.id == lesson_code_id)
            )
            if not lesson_code:
                raise HTTPException(404, "❌ Không tìm thấy bài code")

            testcases = sorted(
                lesson_code.lesson_code_testcases or [],
                key=lambda t: t.order_index or 0,
            )
            if not testcases:
                raise HTTPException(400, "❌ Bài code chưa có testcase nào")

            # 3️⃣ Giới hạn
            time_limit = float(lesson_code.time_limit or 2.0)
            memory_limit = int(lesson_code.memory_limit or 256_000_000)

            # 4️⃣ Chuẩn bị file chạy (main đi trước)
            files = [
                {"name": f.filename, "content": f.content}
                for f in sorted(payload.files, key=lambda x: not x.is_main)
            ]

            results = []

            # 5️⃣ Duyệt từng testcase
            for tc in testcases:
                try:
                    run_result = await self.piston.run_code(
                        language=lang.name,
                        version=lang.version,
                        files=files,
                        stdin=tc.input or "",
                    )

                    run = run_result.get("run", {}) or {}
                    stdout = (run.get("stdout") or "").strip()
                    stderr = (run.get("stderr") or "").strip()
                    exit_code = int(run.get("code", 0))
                    cpu_time = float(run.get("cpu_time", 0))
                    memory = int(run.get("memory", 0))
                    expected = (tc.expected_output or "").strip()

                    # Phân loại kết quả
                    if exit_code != 0 or stderr:
                        verdict = "runtime_error"
                    elif cpu_time > time_limit:
                        verdict = "time_limit_exceeded"
                    elif memory > memory_limit:
                        verdict = "memory_limit_exceeded"
                    elif stdout == expected:
                        verdict = "passed"
                    else:
                        verdict = "failed"
                    if tc.is_sample:
                        results.append(
                            {
                                "id": str(tc.id),  # ✅ thêm id test case
                                "index": tc.order_index or 0,
                                "exit_code": exit_code,
                                "cpu_time": cpu_time,
                                "memory": memory,
                                "language": lang.name,
                                "version": lang.version,
                                "result": verdict,
                                "is_hidden": True,
                            }
                        )
                    else:
                        results.append(
                            {
                                "id": str(tc.id),  # ✅ thêm id test case
                                "index": tc.order_index or 0,
                                "input": tc.input,
                                "expected": expected,
                                "output": stdout,
                                "stderr": stderr,
                                "exit_code": exit_code,
                                "cpu_time": cpu_time,
                                "memory": memory,
                                "language": lang.name,
                                "version": lang.version,
                                "result": verdict,
                                "is_hidden": False,
                            }
                        )

                except Exception as e:
                    logger.error(f"❌ Lỗi khi chạy testcase {tc.id}: {e}")
                    results.append(
                        {
                            "id": str(tc.id),
                            "index": tc.order_index or 0,
                            "result": "internal_error",
                            "error_message": str(e),
                        }
                    )

            # 6️⃣ Tổng kết
            total = len(results)
            passed = sum(1 for r in results if r["result"] == "passed")
            all_passed = passed == total

            # 7️⃣ Nếu pass toàn bộ → lưu code user
            if all_passed:
                logger.info(f"✅ User {user.id} pass toàn bộ test {lesson_code.id}")

                await self.db.execute(
                    update(LessonCodeFiles)
                    .where(
                        LessonCodeFiles.lesson_code_id == lesson_code.id,
                        LessonCodeFiles.user_id == user.id,
                        LessonCodeFiles.role == "user",
                    )
                    .values(is_pass=True, updated_at=await to_utc_naive(get_now()))
                )
                await self.db.commit()

            # 8️⃣ Trả kết quả
            return {
                "status": "passed" if all_passed else "failed",
                "passed": passed,
                "failed": total - passed,
                "total": total,
                "saved": all_passed,
                "language": lang.name,
                "version": lang.version,
                "details": results,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"🔥 Lỗi server khi test code: {e}")
            raise HTTPException(500, f"Lỗi server khi test code: {e}")

    async def get_lesson_start_code_async(self, lesson_id: uuid.UUID, user: User):
        """
        ✅ Lấy nội dung code để hiển thị khi user bắt đầu làm bài:
        - Nếu user đã có code riêng (role='user') → trả code đó
        - Nếu chưa có → trả starter files (role='starter')
        - Chỉ trả danh sách file (id, filename, content, role, is_main)
        """

        try:
            # 1️⃣ Lấy lesson và toàn bộ lesson_codes + lesson_code_files
            lesson = await self.db.scalar(
                select(Lessons)
                .options(
                    selectinload(Lessons.lesson_codes).selectinload(
                        LessonCodes.lesson_code_files
                    )
                )
                .where(Lessons.id == lesson_id)
            )

            if not lesson:
                raise HTTPException(404, "❌ Không tìm thấy bài học")

            lesson_codes = lesson.lesson_codes or []
            if not lesson_codes:
                raise HTTPException(404, "❌ Bài học chưa có bài code nào")

            files_result = []

            # 2️⃣ Lấy tất cả file khởi đầu cho từng bài code
            for code in lesson_codes:
                all_files = code.lesson_code_files or []
                user_files = [
                    f for f in all_files if f.role == "user" and f.user_id == user.id
                ]
                starter_files = [f for f in all_files if f.role == "starter"]

                active_files = user_files if user_files else starter_files

                for f in active_files:
                    files_result.append(
                        {
                            "id": str(f.id),
                            "filename": f.filename,
                            "content": f.content,
                            "role": f.role,
                            "is_main": bool(f.is_main),
                            "lesson_code_id": str(code.id),
                        }
                    )

            # 3️⃣ Nếu không có file nào
            if not files_result:
                raise HTTPException(404, "❌ Không tìm thấy file khởi đầu")

            return {"lesson_id": str(lesson.id), "files": files_result}

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"🔥 Lỗi server khi lấy start code: {e}")
            raise HTTPException(500, f"Lỗi server khi lấy start code: {e}")

    # 🧠 Chạy nền nhúng embedding
    @staticmethod
    async def _process_embedding_background(note_id: uuid.UUID):

        async with AsyncSessionLocal() as db:
            try:
                note = await db.scalar(
                    select(LessonNotes).where(LessonNotes.id == note_id)
                )
                if not note or not note.content.strip():
                    return

                embedding_service = await get_embedding_service()
                vector = await embedding_service.embed_google_normalized(note.content)

                note.embedding = vector
                note.created_at = get_now()
                await db.commit()

                print(f"✅ Đã nhúng embedding cho note {note_id}")
            except Exception as e:
                await db.rollback()
                print(f"❌ Lỗi khi nhúng embedding note {note_id}: {e}")

    # ✏️ Tạo ghi chú cho bài học
    async def create_lesson_note_async(
        self,
        lesson_id: uuid.UUID,
        schema: CreateLessonNote,
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks,
    ):
        try:
            # 1️⃣ Kiểm tra bài học tồn tại
            lesson = await self.db.scalar(
                select(Lessons).where(Lessons.id == lesson_id)
            )
            if not lesson:
                raise HTTPException(404, f"Không tìm thấy bài học {lesson_id}")

            # 2️⃣ Tạo ghi chú
            new_note = LessonNotes(
                id=uuid.uuid4(),
                lesson_id=lesson_id,
                user_id=user_id,
                time_seconds=schema.time_seconds,
                content=schema.content.strip(),
                created_at=await to_utc_naive(get_now()),
            )

            self.db.add(new_note)
            await self.db.commit()
            await self.db.refresh(new_note)

            # 3️⃣ Gọi nền nhúng embedding (async)
            background_tasks.add_task(
                LearningService._process_embedding_background, new_note.id
            )

            return {
                "message": "Tạo ghi chú thành công",
                "id": new_note.id,
                "status": "embedding_processing",
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo ghi chú: {e}")

    async def get_notes_by_lesson_and_user_async(
        self,
        lesson_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        try:
            query = (
                select(LessonNotes)
                .where(
                    LessonNotes.lesson_id == lesson_id,
                    LessonNotes.user_id == user_id,
                )
                .order_by(asc(LessonNotes.time_seconds))
            )
            result = await self.db.execute(query)
            notes = result.scalars().all()

            return [
                {
                    "id": str(note.id),
                    "lesson_id": str(note.lesson_id),
                    "time_seconds": float(note.time_seconds),
                    "content": note.content,
                    "created_at": note.created_at.isoformat(),
                }
                for note in notes
            ]

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy ghi chú: {e}")

    async def delete_note_async(self, note_id: uuid.UUID, user_id: uuid.UUID):
        try:
            result = await self.db.execute(
                delete(LessonNotes)
                .where(
                    LessonNotes.id == note_id,
                    LessonNotes.user_id == user_id,
                )
                .returning(LessonNotes.id)
            )
            deleted = result.scalar()
            if not deleted:
                raise HTTPException(
                    404, "Không tìm thấy ghi chú hoặc bạn không có quyền xóa"
                )

            await self.db.commit()
            return {"message": "Xóa ghi chú thành công", "id": str(deleted)}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi xóa ghi chú: {e}")

    async def update_note_async(
        self,
        note_id: uuid.UUID,
        user_id: uuid.UUID,
        schema: UpdateLessonNote,
    ):
        try:
            note = await self.db.scalar(
                select(LessonNotes).where(
                    LessonNotes.id == note_id,
                    LessonNotes.user_id == user_id,
                )
            )
            if not note:
                raise HTTPException(
                    404, "Không tìm thấy ghi chú hoặc bạn không có quyền sửa"
                )

            note.content = schema.content.strip()
            if schema.time_seconds is not None:
                note.time_seconds = float(schema.time_seconds)

            await self.db.commit()
            await self.db.refresh(note)

            return {
                "message": "Cập nhật ghi chú thành công",
                "note": {
                    "id": str(note.id),
                    "lesson_id": str(note.lesson_id),
                    "time_seconds": note.time_seconds,
                    "content": note.content,
                    "updated_at": note.created_at.isoformat(),
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi cập nhật ghi chú: {e}")

    async def get_lesson_comments_async(
        self,
        lesson_id: uuid.UUID,
        current_user_id: Optional[uuid.UUID] = None,
        root_id: Optional[uuid.UUID] = None,
        depth_target: int = 0,
        limit: int = 10,
        cursor: Optional[str] = None,
    ):
        """
        API: Lấy bình luận theo cấp (depth)
        - depth_target = 0 → comment gốc
        - depth_target = 1 → reply cấp 1 theo root_id
        - depth_target >= 2 → thread sâu hơn theo root_id
        Thêm thông tin reaction (chỉ 1 loại duy nhất, không có reaction_type)
        """
        try:
            # 🧠 Lấy id giảng viên của khóa học
            author_stmt = (
                select(Courses.instructor_id)
                .join(Lessons, Lessons.course_id == Courses.id)
                .where(Lessons.id == lesson_id)
            )
            author_id = await self.db.scalar(author_stmt)

            # 🎯 Truy vấn bình luận theo cấp độ
            stmt = select(LessonComments).options(selectinload(LessonComments.user))

            if depth_target == 0:
                stmt = stmt.where(
                    LessonComments.lesson_id == lesson_id,
                    LessonComments.depth == 0,
                ).order_by(desc(LessonComments.created_at))
                cursor_dir_desc = True
            elif depth_target == 1:
                if not root_id:
                    raise HTTPException(400, "Thiếu root_id khi truy vấn cấp 1")
                stmt = stmt.where(
                    LessonComments.root_id == root_id,
                    LessonComments.depth == 1,
                ).order_by(asc(LessonComments.created_at))
                cursor_dir_desc = False
            else:
                if not root_id:
                    raise HTTPException(400, "Thiếu root_id khi truy vấn cấp ≥2")
                stmt = stmt.where(
                    LessonComments.root_id == root_id,
                    LessonComments.depth >= 2,
                ).order_by(asc(LessonComments.created_at))
                cursor_dir_desc = False

            # ⏱ Cursor-based pagination
            if cursor:
                try:
                    cursor_dt = datetime.fromisoformat(cursor)
                    # Đảm bảo cursor_dt là naive (vì LessonComments.created_at là timezone-aware)
                    # PostgreSQL sẽ tự convert, nhưng để tránh lỗi trong Python ta chuyển về naive
                    from app.libs.formats.datetime import VIETNAM_TIMEZONE

                    if cursor_dt.tzinfo is not None:
                        # Nếu có timezone, chuyển sang UTC+7 rồi bỏ tzinfo
                        cursor_dt = cursor_dt.astimezone(VIETNAM_TIMEZONE).replace(
                            tzinfo=None
                        )
                    else:
                        # Nếu là naive, giữ nguyên (giả định đã là UTC+7)
                        cursor_dt = cursor_dt
                except ValueError:
                    raise HTTPException(400, "Cursor không hợp lệ (ISO8601)")
                if cursor_dir_desc:
                    stmt = stmt.where(LessonComments.created_at < cursor_dt)
                else:
                    stmt = stmt.where(LessonComments.created_at > cursor_dt)

            stmt = stmt.limit(limit + 1)
            rows = (await self.db.scalars(stmt)).all()

            has_next = len(rows) > limit
            rows = rows[:limit]
            next_cursor = rows[-1].created_at.isoformat() if has_next and rows else None

            if not rows:
                return {
                    "type": f"level_{depth_target}_comments",
                    "root_id": str(root_id) if root_id else None,
                    "items": [],
                    "next_cursor": None,
                    "has_next": False,
                }

            # 📊 Đếm reply cấp con
            count_map = {}
            if depth_target == 0:
                root_ids = [r.id for r in rows]
                res = await self.db.execute(
                    select(LessonComments.root_id, func.count())
                    .where(
                        LessonComments.root_id.in_(root_ids),
                        LessonComments.depth > 0,
                    )
                    .group_by(LessonComments.root_id)
                )
                count_map = {str(rid): int(cnt) for rid, cnt in res.fetchall()}
            elif depth_target == 1:
                parent_ids = [r.id for r in rows]
                res = await self.db.execute(
                    select(LessonComments.parent_id, func.count())
                    .where(
                        LessonComments.parent_id.in_(parent_ids),
                        LessonComments.depth == 2,
                    )
                    .group_by(LessonComments.parent_id)
                )
                count_map = {str(pid): int(cnt) for pid, cnt in res.fetchall()}

            # ❤️ Kiểm tra reaction
            comment_ids = [r.id for r in rows]
            res_react = await self.db.execute(
                select(LessonCommentReactions.comment_id, func.count())
                .where(LessonCommentReactions.comment_id.in_(comment_ids))
                .group_by(LessonCommentReactions.comment_id)
            )
            react_map = {str(cid): int(cnt) for cid, cnt in res_react.fetchall()}

            my_react_set = set()
            if current_user_id:
                res_my = await self.db.execute(
                    select(LessonCommentReactions.comment_id).where(
                        LessonCommentReactions.comment_id.in_(comment_ids),
                        LessonCommentReactions.user_id == current_user_id,
                    )
                )
                my_react_set = {str(cid) for (cid,) in res_my.fetchall()}

            # 🧱 Chuẩn hóa dữ liệu trả về
            items = []
            for c in rows:
                cid = str(c.id)
                items.append(
                    {
                        "id": cid,
                        "root_id": str(c.root_id),
                        "parent_id": str(c.parent_id) if c.parent_id else None,
                        "lesson_id": str(c.lesson_id),
                        "user_id": str(c.user_id),
                        "user_name": getattr(c.user, "fullname", None),
                        "user_avatar": getattr(c.user, "avatar", None),
                        "content": c.content,
                        "depth": c.depth,
                        "created_at": c.created_at.isoformat(),
                        "reply_count_all": (
                            int(count_map.get(cid, 0)) if depth_target <= 1 else 0
                        ),
                        "is_owner": c.user_id == current_user_id,
                        "is_author": c.user_id == author_id,
                        "reactions": {
                            "total": int(react_map.get(cid, 0)),
                            "has_reacted": cid in my_react_set,
                        },
                    }
                )

            return {
                "type": f"level_{depth_target}_comments",
                "root_id": str(root_id) if root_id else None,
                "items": items,
                "next_cursor": next_cursor,
                "has_next": has_next,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Lỗi khi lấy bình luận: {e}")

    async def get_list_react_by_comment_id(
        self,
        comment_id: uuid.UUID,
    ):
        """
        Lấy danh sách user đã thả reaction cho một bình luận.
        (Giả định: mỗi record trong lesson_comment_reactions tương ứng 1 user reaction duy nhất)
        """
        try:
            stmt = (
                select(LessonCommentReactions)
                .options(
                    selectinload(LessonCommentReactions.user),
                    selectinload(LessonCommentReactions.comment),
                )
                .where(LessonCommentReactions.comment_id == comment_id)
                .order_by(desc(LessonCommentReactions.created_at))
            )

            reactions = (await self.db.scalars(stmt)).all()

            if not reactions:
                return []

            return [
                {
                    "id": str(r.id),
                    "comment_id": str(r.comment_id),
                    "user_id": str(r.user_id),
                    "user_name": getattr(r.user, "fullname", None),
                    "user_avatar": getattr(r.user, "avatar", None),
                    "is_owner": r.user_id
                    == r.comment.user_id,  # user là tác giả comment
                    "created_at": r.created_at.isoformat(),
                }
                for r in reactions
            ]

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy danh sách reaction: {e}")

    async def toggle_comment_reaction_async(
        self,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """
        Thả / bỏ thả tym cho bình luận (HTTP + realtime broadcast)
        Trả về định dạng:
        {
          "type": "comment_reacted",
          "comment_id": "...",
          "lesson_id": "...",
          "reactions": {
              "total": 1,
              "has_reacted": true
          }
        }
        """
        try:
            # ✅ Kiểm tra bình luận tồn tại
            comment = await self.db.scalar(
                select(LessonComments).where(LessonComments.id == comment_id)
            )
            if not comment:
                raise HTTPException(404, "Bình luận không tồn tại")

            # ✅ Kiểm tra user đã thả tym chưa
            existing = await self.db.scalar(
                select(LessonCommentReactions).where(
                    LessonCommentReactions.comment_id == comment_id,
                    LessonCommentReactions.user_id == user_id,
                )
            )

            # 🩶 Nếu đã có → bỏ thả tym
            if existing:
                await self.db.delete(existing)
                await self.db.commit()

                # Đếm lại tổng
                total = (
                    await self.db.scalar(
                        select(func.count()).where(
                            LessonCommentReactions.comment_id == comment_id
                        )
                    )
                    or 0
                )

                result = {
                    "type": "comment_unreacted",
                    "comment_id": str(comment_id),
                    "lesson_id": str(comment.lesson_id),
                    "reactions": {
                        "total": total,
                        "has_reacted": False,
                    },
                }

                await ws_manager.broadcast(
                    f"lesson_comment_ws_lesson_id_{comment.lesson_id}", result
                )
                return result

            # ❤️ Nếu chưa → thêm mới
            new_reaction = LessonCommentReactions(
                comment_id=comment_id,
                user_id=user_id,
            )
            self.db.add(new_reaction)
            await self.db.commit()
            await self.db.refresh(new_reaction)

            total = (
                await self.db.scalar(
                    select(func.count()).where(
                        LessonCommentReactions.comment_id == comment_id
                    )
                )
                or 1
            )

            result = {
                "type": "comment_reacted",
                "comment_id": str(comment_id),
                "lesson_id": str(comment.lesson_id),
                "reactions": {
                    "total": total,
                    "has_reacted": True,
                },
            }

            await ws_manager.broadcast(
                f"lesson_comment_ws_lesson_id_{comment.lesson_id}", result
            )
            return result

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi xử lý thả tym: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    @staticmethod
    async def create_lesson_comment_async(
        lesson_id: uuid.UUID,
        schema: CreateLessonComment,
        user: User,
    ):
        async with AsyncSessionLocal() as db:
            try:
                depth = 0
                root_id = None

                # Nếu có parent → xác định root và depth
                if schema.parent_id:
                    parent = await db.scalar(
                        select(LessonComments).where(
                            LessonComments.id == schema.parent_id
                        )
                    )
                    if not parent:
                        return {"error": "Bình luận cha không tồn tại"}

                    # Nếu người dùng truyền nhầm id cấp 2 thì fix về depth=2, root_id của cấp 1
                    if parent.depth >= 1:
                        depth = 2
                        root_id = parent.root_id or parent.id
                    else:
                        depth = 1
                        root_id = parent.id

                # Tạo bình luận mới
                new_comment = LessonComments(
                    lesson_id=lesson_id,
                    user_id=user.id,
                    parent_id=schema.parent_id,
                    root_id=root_id,
                    content=schema.content.strip(),
                    depth=depth,
                    created_at=await to_utc_naive(get_now()),
                    updated_at=await to_utc_naive(get_now()),
                )

                db.add(new_comment)
                await db.flush()

                if not new_comment.root_id:
                    new_comment.root_id = new_comment.id

                await db.commit()
                await db.refresh(new_comment)
                return {
                    "type": "comment_created",
                    "comment": {
                        "id": str(new_comment.id),
                        "lesson_id": str(new_comment.lesson_id),
                        "root_id": str(new_comment.root_id),
                        "user_id": str(new_comment.user_id),
                        "user_avatar": user.avatar,
                        "user_name": user.fullname,
                        "parent_id": (
                            str(new_comment.parent_id)
                            if new_comment.parent_id
                            else None
                        ),
                        "content": new_comment.content,
                        "status": new_comment.status,
                        "depth": new_comment.depth,
                        "created_at": new_comment.created_at.isoformat(),
                        "updated_at": (
                            new_comment.updated_at.isoformat()
                            if new_comment.updated_at
                            else None
                        ),
                    },
                }

            except Exception as e:
                await db.rollback()
                return {"error": f"Lỗi khi tạo bình luận: {e}"}

    @staticmethod
    async def update_lesson_comment_async(
        comment_id: uuid.UUID, schema: UpdateLessonComment, user
    ):

        async with AsyncSessionLocal() as db:
            try:
                # 1) Tồn tại?
                comment = await db.scalar(
                    select(LessonComments).where(LessonComments.id == comment_id)
                )
                if not comment:
                    return {"error": "Không tìm thấy bình luận", "code": 404}

                # 2) Chính chủ?
                if str(comment.user_id) != str(user.id):
                    return {
                        "error": "Bạn không thể sửa bình luận của người khác",
                        "code": 403,
                    }

                # 3) Validate & cập nhật
                new_content = (schema.content or "").strip()
                if not new_content:
                    return {"error": "Nội dung không được rỗng", "code": 422}

                comment.content = new_content
                comment.updated_at = get_now()  # ✅ không await

                await db.commit()
                await db.refresh(comment)

                # 4) Trả về cùng format với create
                return {
                    "type": "comment_updated",
                    "comment": {
                        "id": str(comment.id),
                        "lesson_id": str(comment.lesson_id),
                        "root_id": str(comment.root_id) if comment.root_id else None,
                        "user_id": str(comment.user_id),
                        "user_avatar": getattr(user, "avatar", None),
                        "user_name": getattr(user, "fullname", None),
                        "parent_id": (
                            str(comment.parent_id) if comment.parent_id else None
                        ),
                        "content": comment.content,
                        "status": comment.status,
                        "depth": comment.depth,
                        "created_at": (
                            comment.created_at.isoformat()
                            if comment.created_at
                            else None
                        ),
                        "updated_at": (
                            comment.updated_at.isoformat()
                            if comment.updated_at
                            else None
                        ),
                    },
                }

            except Exception as e:
                await db.rollback()
                return {"error": f"Lỗi khi cập nhật bình luận: {e}", "code": 500}

    @staticmethod
    async def delete_lesson_comment_async(
        comment_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ):
        """
        Xóa bình luận:
        - Nếu bình luận có reply → đổi sang hidden (soft-hide).
        - Nếu không có reply → xóa hẳn (hard-delete).
        Yêu cầu: chỉ chính chủ (hoặc tuỳ bạn mở rộng quyền ADMIN/MOD sau).
        """
        from app.db.models.database import (
            LessonComments,  # đảm bảo FK reactions ON DELETE CASCADE
        )
        from app.db.sesson import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                # 1) Lấy comment
                comment = await db.get(LessonComments, comment_id)
                if not comment:
                    return {"error": "Bình luận không tồn tại", "code": 404}

                # 2) Quyền: chính chủ
                if str(comment.user_id) != str(current_user_id):
                    return {
                        "error": "Bạn không có quyền xóa bình luận này",
                        "code": 403,
                    }

                # 3) Có con không? (tối ưu với EXISTS)
                has_child = await db.scalar(
                    select(exists().where(LessonComments.parent_id == comment_id))
                )

                if has_child:
                    # 3a) Có reply → ẩn bình luận (soft-hide)
                    # KHÔNG đụng tới reactions / FK để tránh NOT NULL violation
                    comment.status = "hidden"
                    # chỉ thay content nếu bạn muốn làm “ghost”
                    comment.content = "[Bình luận đã bị ẩn]"
                    comment.updated_at = get_now()
                    await db.commit()
                    await db.refresh(comment)

                    return {
                        "type": "comment_hidden",
                        "comment": {
                            "id": str(comment.id),
                            "lesson_id": str(comment.lesson_id),
                            "root_id": (
                                str(comment.root_id) if comment.root_id else None
                            ),
                            "parent_id": (
                                str(comment.parent_id) if comment.parent_id else None
                            ),
                            "status": comment.status,
                            "content": comment.content,
                            "updated_at": (
                                comment.updated_at.isoformat()
                                if comment.updated_at
                                else None
                            ),
                        },
                        "message": "Bình luận đã bị ẩn do có phản hồi con",
                    }

                # 3b) Không có reply → xóa hẳn
                await db.execute(
                    delete(LessonCommentReactions).where(
                        LessonComments.id == comment_id
                    )
                )
                await db.delete(comment)  # để DB ON DELETE CASCADE xoá reactions
                await db.commit()

                return {
                    "type": "comment_deleted",
                    "comment": {"id": str(comment_id)},
                    "message": "Đã xóa bình luận thành công",
                }

            except Exception as e:
                await db.rollback()
                return {"error": f"Lỗi khi xóa bình luận: {e}", "code": 500}
