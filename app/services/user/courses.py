import json
import uuid
from datetime import datetime, timedelta

import numpy as np
from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import AuthorizationService
from app.core.embedding import EmbeddingService, get_embedding_service
from app.db.models.database import (
    Categories,
    CourseEnrollments,
    CourseFavourites,
    CourseReviews,
    Courses,
    CourseSections,
    Lessons,
    LessonVideos,
    User,
)
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import strip_tz
from app.schemas.lecturer.courses import CourseReview
from app.schemas.shares.notification import NotificationCreateSchema
from app.services.shares.notification import NotificationService
from app.services.user.category import CategoryService


class CoursePublicService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db
        self.embedding = embedding

    async def review_course_async(
        self,
        course_id: uuid.UUID,
        background_tasks: BackgroundTasks,
        schema: CourseReview,
        user: User,
    ):
        try:
            # 1️⃣ Kiểm tra khóa học tồn tại
            course = await self.db.get(Courses, course_id)
            if course is None:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            # 2️⃣ Kiểm tra người dùng đã đăng ký khóa học
            enrolled = await self.db.scalar(
                select(CourseEnrollments).where(
                    CourseEnrollments.course_id == course_id,
                    CourseEnrollments.user_id == user.id,
                )
            )
            if enrolled is None:
                raise HTTPException(
                    status_code=403, detail="Người dùng chưa đăng ký khóa học này"
                )

            # 3️⃣ Kiểm tra người dùng đã đánh giá trước đó chưa
            existing_review = await self.db.scalar(
                select(CourseReviews).where(
                    CourseReviews.course_id == course_id,
                    CourseReviews.user_id == user.id,
                )
            )
            if existing_review:
                raise HTTPException(
                    status_code=409, detail="Bạn đã đánh giá khóa học này trước đó"
                )

            # 4️⃣ Tạo review mới
            new_course_review = CourseReviews(
                course_id=course_id,
                user_id=user.id,
                rating=schema.rating,
                content=schema.content,
            )
            if schema.content:
                # 🧩 Embedding (chuyển văn bản thành vector)
                new_course_review.embedding = (
                    await self.embedding.embed_google_normalized(schema.content)
                )

                # 💬 Sentiment
                sentiment_prompt = (
                    f"Phân tích cảm xúc đoạn văn sau và trả về 1 trong 3 giá trị: "
                    f"positive, neutral, negative:\n\n{schema.content}"
                )
                sentiment_result = await self.embedding.call_model(sentiment_prompt)
                new_course_review.sentiment = sentiment_result.strip().lower()

                # 🧠 Topics
                topics_prompt = f"""
                Trích xuất tối đa 5 chủ đề chính (topics) từ đoạn đánh giá sau.
                Chỉ trả về danh sách dạng JSON mảng string, không giải thích thêm.

                Đánh giá:
                {schema.content}
                """
                topics_text = await self.embedding.call_model(topics_prompt)

                try:
                    topics = json.loads(topics_text)
                    if isinstance(topics, list):
                        new_course_review.topics = topics
                except json.JSONDecodeError:
                    new_course_review.topics = []  # fallback nếu AI trả về lỗi

            # 6️⃣ Lưu vào DB
            self.db.add(new_course_review)
            background_tasks.add_task(
                self.embedding.update_user_embedding_adaptive,
                user.id,
                course.embedding,
                "wishlist",
                course_id,
            )
            await self.db.flush()

            # ✅ CẬP NHẬT THỐNG KÊ RATING CHO KHÓA HỌC
            # Tính lại rating_avg dựa trên tất cả review
            rating_stats = await self.db.execute(
                select(
                    func.avg(CourseReviews.rating).label("avg_rating"),
                    func.count(CourseReviews.id).label("count")
                ).where(CourseReviews.course_id == course_id)
            )
            stats_row = rating_stats.first()
            if stats_row:
                from decimal import Decimal
                new_avg = Decimal(str(round(stats_row.avg_rating or 0, 2)))
                new_count = stats_row.count or 0

                course.rating_avg = new_avg
                course.rating_count = new_count
                course.total_reviews = new_count

            # ✅ CẬP NHẬT EVALUATED_COUNT CHO INSTRUCTOR
            instructor = await self.db.scalar(
                select(User).where(User.id == course.instructor_id)
            )
            if instructor:
                instructor.evaluated_count = (instructor.evaluated_count or 0) + 1

                # Tính lại rating_avg của instructor (trung bình rating của tất cả khóa học)
                instructor_rating_stats = await self.db.execute(
                    select(func.avg(Courses.rating_avg).label("avg"))
                    .where(
                        Courses.instructor_id == instructor.id,
                        Courses.rating_avg.isnot(None),
                        Courses.rating_count > 0,
                    )
                )
                instructor_avg_row = instructor_rating_stats.first()
                if instructor_avg_row and instructor_avg_row.avg:
                    instructor.rating_avg = round(float(instructor_avg_row.avg), 2)

            await self.db.commit()
            await self.db.refresh(new_course_review)

            # ✅ GỬI THÔNG BÁO CHO INSTRUCTOR KHI CÓ ĐÁNH GIÁ MỚI
            notification_service = NotificationService(self.db)
            await notification_service.create_notification_async(
                NotificationCreateSchema(
                    user_id=course.instructor_id,
                    title="⭐ Có đánh giá mới cho khóa học",
                    content=f"Học viên {user.fullname or 'Ẩn danh'} đã đánh giá {schema.rating}⭐ cho khóa học \"{course.title}\".",
                    type="course",
                    role_target=["LECTURER"],
                    url=f"/lecturer/courses/{course.id}/reviews",
                    metadata={"course_id": str(course.id), "review_id": str(new_course_review.id)}
                )
            )

            return {
                "message": "Đánh giá khóa học thành công",
                "review_id": str(new_course_review.id),
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi tạo review khóa học {course_id}: {e}"
            )

    async def get_course_detail_info_async(
        self, course_id: uuid.UUID, user: User | None
    ):
        try:
            course: Courses | None = await self.db.scalar(
                select(Courses)
                .where(Courses.id == course_id)
                .options(selectinload(Courses.instructor))
            )
            if course is None:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")
            course_existing_favourite = None
            if user is not None:
                course_existing_favourite = await self.db.scalar(
                    select(CourseFavourites).where(
                        CourseFavourites.course_id == course_id,
                        CourseFavourites.user_id == user.id,
                    )
                )

            return {
                "id": str(course.id),
                "title": course.title,
                "description": course.description,
                "level": course.level,
                "language": course.language,
                "last_updated": course.updated_at,
                "rating": course.rating_avg,
                "rating_count": course.rating_count,
                "total_enrolls": course.total_enrolls,
                "views": course.views,
                "is_favourite": bool(course_existing_favourite),
                "thumbnail_url": course.thumbnail_url,
                "outcomes": course.outcomes,
            }
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy thông tin chi tiết khóa học: {str(e)}",
            )

    async def check_user_enrollment_async(
        self, course_id: uuid.UUID, user: User
    ) -> bool:
        try:
            enrollment = await self.db.scalar(
                select(CourseEnrollments).where(
                    CourseEnrollments.course_id == course_id,
                    CourseEnrollments.user_id == user.id,
                )
            )
            return enrollment is not None
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Lỗi khi kiểm tra đăng ký khóa học: {str(e)}"
            )

    async def get_course_detail_info_by_slug_async(
        self, course_slug: str, user: User | None
    ):
        try:
            # 1️⃣ Lấy khóa học + quan hệ liên quan
            stmt_course = (
                select(Courses)
                .where(Courses.slug == course_slug)
                .options(
                    selectinload(Courses.instructor),
                    selectinload(Courses.category),
                    selectinload(Courses.course_sections).selectinload(
                        CourseSections.lessons
                    ),
                )
            )
            course: Courses | None = await self.db.scalar(stmt_course)
            if course is None:
                raise HTTPException(status_code=404, detail="Khóa học không tồn tại")

            # 2️⃣ Tính toán tag (Thịnh hành, Bán chạy, Đánh giá cao)
            stmt_all = select(
                Courses.id, Courses.views, Courses.total_enrolls, Courses.rating_avg
            ).where(Courses.is_published.is_(True))
            result_all = await self.db.execute(stmt_all)
            data = result_all.mappings().all()
            tags = []
            if data:
                views_cutoff = np.percentile([r["views"] or 0 for r in data], 80)
                enrolls_cutoff = np.percentile(
                    [r["total_enrolls"] or 0 for r in data], 80
                )
                rating_cutoff = np.percentile(
                    [float(r["rating_avg"] or 0) for r in data], 80
                )
                if course.views and course.views > views_cutoff:
                    tags.append("Thịnh hành nhất")
                if course.total_enrolls and course.total_enrolls > enrolls_cutoff:
                    tags.append("Bán chạy nhất")
                if course.rating_avg and float(course.rating_avg) > rating_cutoff:
                    tags.append("Đánh giá cao nhất")

            # 3️⃣ Chuỗi danh mục cha (chain)
            chain = []
            current_id = course.category_id
            while current_id:
                category = await self.db.scalar(
                    select(Categories).where(Categories.id == current_id)
                )
                if not category:
                    break
                chain.append(category)
                current_id = category.parent_id
            chain.reverse()

            # 4️⃣ Lấy 4 review mẫu
            stmt_reviews = (
                select(CourseReviews)
                .options(selectinload(CourseReviews.user))
                .where(CourseReviews.course_id == course.id)
                .order_by(CourseReviews.rating.desc())
                .limit(4)
            )
            course_reviews = (await self.db.scalars(stmt_reviews)).all()

            # 5️⃣ Lấy video cho tất cả lesson trong khóa học
            lesson_ids = [
                lesson.id
                for section in course.course_sections
                for lesson in section.lessons
            ]
            video_map = {}
            if lesson_ids:
                result_videos = await self.db.execute(
                    select(
                        LessonVideos.lesson_id,
                        LessonVideos.video_url,
                        LessonVideos.duration,
                        LessonVideos.transcript,
                    ).where(LessonVideos.lesson_id.in_(lesson_ids))
                )
                video_map = {r.lesson_id: r for r in result_videos.fetchall()}

            # 6️⃣ Kiểm tra nếu chưa có bài học nào
            has_lessons = any(section.lessons for section in course.course_sections)
            if not has_lessons:
                return {
                    "status": "empty",
                    "message": "Khóa học này chưa có bài học nào. Hãy quay lại sau!",
                    "course": {
                        "id": str(course.id),
                        "title": course.title,
                        "slug": course.slug,
                        "thumbnail_url": course.thumbnail_url,
                        "description": course.description,
                        "instructor": (
                            {
                                "id": str(course.instructor.id),
                                "fullname": course.instructor.fullname,
                                "avatar": course.instructor.avatar,
                            }
                            if course.instructor
                            else None
                        ),
                    },
                }

            # 7️⃣ Trả dữ liệu chi tiết
            return {
                "status": "ok",
                "course": {
                    "id": str(course.id),
                    "title": course.title,
                    "tags": tags,
                    "description": course.description,
                    "level": course.level,
                    "language": course.language,
                    "last_updated": course.updated_at,
                    "rating": course.rating_avg,
                    "slug": course.slug,
                    "rating_count": course.rating_count,
                    "total_enrolls": course.total_enrolls,
                    "views": course.views,
                    "thumbnail_url": course.thumbnail_url,
                    "outcomes": course.outcomes,
                    "currency": course.currency,
                    "base_price": course.base_price,
                    "requirements": course.requirements,
                    "target_audience": course.target_audience,
                    "promo_video_url": course.promo_video_url,
                    "instructor": (
                        {
                            "id": str(course.instructor.id),
                            "fullname": course.instructor.fullname,
                            "avatar": course.instructor.avatar,
                            "instructor_description": course.instructor.instructor_description,
                            "student_count": course.instructor.student_count,
                            "course_count": course.instructor.course_count,
                            "rating_avg": course.instructor.rating_avg,
                            "evaluated_count": course.instructor.evaluated_count,
                        }
                        if course.instructor
                        else None
                    ),
                    "sections": [
                        {
                            "id": str(section.id),
                            "title": section.title,
                            "position": section.position,
                            "lessons": [
                                {
                                    "id": str(lesson.id),
                                    "title": lesson.title,
                                    "lesson_type": lesson.lesson_type,
                                    "position": lesson.position,
                                    "is_preview": lesson.is_preview,
                                    "duration": (
                                        video_map.get(lesson.id, None).duration
                                        if video_map.get(lesson.id, None) is not None
                                        else None
                                    ),
                                }
                                for lesson in sorted(
                                    section.lessons, key=lambda l: l.position
                                )
                            ],
                        }
                        for section in sorted(
                            course.course_sections, key=lambda s: s.position
                        )
                    ],
                },
                "category_chain": [
                    {"id": str(cat.id), "name": cat.name, "slug": cat.slug}
                    for cat in chain
                ],
                "sample_reviews": [
                    {
                        "id": str(review.id),
                        "user_id": str(review.user.id) if review.user else None,
                        "user_fullname": review.user.fullname if review.user else None,
                        "user_avatar": review.user.avatar if review.user else None,
                        "rating": review.rating,
                        "content": review.content,
                        "created_at": review.created_at,
                    }
                    for review in course_reviews
                ],
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy thông tin chi tiết khóa học: {str(e)}",
            )

    async def get_all_lesson_preview_async(self, course_id: uuid.UUID):
        try:
            results = await self.db.execute(
                select(Lessons)
                .where(
                    Lessons.course_id == course_id,
                    Lessons.is_preview.is_(True),
                )
                .order_by(Lessons.position)
            )
            lesson_previews = results.scalars().all()
            if not lesson_previews:
                raise HTTPException(404, "Không tìm thấy bài học xem trước nào")

            lesson_ids = [lesson.id for lesson in lesson_previews]
            video_map = {}
            if lesson_ids:
                result_videos = await self.db.execute(
                    select(
                        LessonVideos.lesson_id,
                        LessonVideos.video_url,
                        LessonVideos.duration,
                    ).where(LessonVideos.lesson_id.in_(lesson_ids))
                )
                video_map = {r.lesson_id: r for r in result_videos.fetchall()}

            return [
                {
                    "id": str(lesson.id),
                    "title": lesson.title,
                    "lesson_type": lesson.lesson_type.value if hasattr(lesson.lesson_type, 'value') else lesson.lesson_type,
                    "position": lesson.position,
                    "is_preview": lesson.is_preview,
                    "video_url": (
                        video_map[lesson.id].video_url if lesson.id in video_map else None
                    ),
                    "duration": (
                        video_map[lesson.id].duration if lesson.id in video_map else None
                    ),
                }
                for lesson in lesson_previews
            ]

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi lấy bài học xem trước: {str(e)}")

    async def enroll_in_course_async(
        self,
        course_id: uuid.UUID,
        background_tasks: BackgroundTasks,
        user: User,
    ):
        try:
            # ===== Lấy khóa học =====
            course: Courses | None = await self.db.get(Courses, course_id)
            if course is None:
                raise HTTPException(404, "Khóa học không tồn tại")

            # ===== Kiểm tra đã đăng ký chưa =====
            course_enroll = await self.db.scalar(
                select(CourseEnrollments).where(
                    CourseEnrollments.course_id == course_id,
                    CourseEnrollments.user_id == user.id,
                )
            )
            if course_enroll is not None:
                raise HTTPException(409, "Bạn đã đăng ký khóa học này trước đó")

            # ===== Case 1: Giảng viên tự đăng ký khóa học của chính mình =====
            if course.instructor_id == user.id:
                enroll = CourseEnrollments(
                    course_id=course_id,
                    user_id=user.id,
                )
                self.db.add(enroll)
                await self.db.commit()

                return {
                    "message": "Giảng viên đã tự đăng ký học thành công (không tính doanh thu)"
                }

            # ===== Case 2: Khóa học miễn phí =====
            if course.base_price == 0:
                enroll = CourseEnrollments(
                    course_id=course_id,
                    user_id=user.id,
                )
                self.db.add(enroll)
                await self.db.flush()

                # ✅ CẬP NHẬT COURSES.TOTAL_ENROLLS
                course.total_enrolls = (course.total_enrolls or 0) + 1

                # ✅ CẬP NHẬT USER.STUDENT_COUNT CHO INSTRUCTOR
                # Chỉ tăng nếu user này chưa từng đăng ký bất kỳ khóa học nào của instructor
                instructor = await self.db.scalar(
                    select(User).where(User.id == course.instructor_id)
                )
                if instructor:
                    # Kiểm tra xem user đã là học viên của instructor này chưa
                    existing_enrollment_count = await self.db.scalar(
                        select(func.count())
                        .select_from(CourseEnrollments)
                        .join(Courses, Courses.id == CourseEnrollments.course_id)
                        .where(
                            CourseEnrollments.user_id == user.id,
                            Courses.instructor_id == instructor.id,
                        )
                    )
                    # Nếu đây là lần đầu (count = 1, vì vừa flush enroll mới), tăng student_count
                    if existing_enrollment_count == 1:
                        instructor.student_count = (instructor.student_count or 0) + 1

                await self.db.commit()

                # =====================================================
                # 🔔 SEND NOTIFICATION (student + instructor)
                # =====================================================
                notification_service = NotificationService(self.db)
                roles = await AuthorizationService.get_list_role_in_user(user)

                # Noti cho HỌC VIÊN
                await notification_service.create_notification_async(
                    NotificationCreateSchema(
                        user_id=user.id,
                        roles=roles,
                        title="Đăng ký khóa học thành công 🎉",
                        content=f"Bạn đã đăng ký khóa học '{course.title}' (miễn phí).",
                        url=f"/learning/{course.slug}",
                        type="course",
                        role_target=["USER"],
                        metadata={"course_id": str(course.id)},
                        action="open_url",
                    )
                )

                # Noti cho GIẢNG VIÊN
                await notification_service.create_notification_async(
                    NotificationCreateSchema(
                        user_id=course.instructor_id,
                        roles=["LECTURER"],
                        title=f"Học viên mới đăng ký khóa học '{course.title}' 🎉",
                        content=f"{user.fullname} ({user.email}) vừa đăng ký khóa học miễn phí của bạn.",
                        url=f"/instructor/courses/{course.id}",
                        type="course",
                        role_target=["LECTURER"],
                        metadata={
                            "course_id": str(course.id),
                            "student_id": str(user.id),
                        },
                        action="open_url",
                    )
                )

                return {"message": "Đăng ký thành công"}

            # ===== Case 3: Khóa học có phí → FE phải gọi checkout =====
            raise HTTPException(402, "Khóa học có phí, vui lòng tiến hành thanh toán")

        except HTTPException:
            raise

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Đã xảy ra lỗi: {e}")

    async def check_user_enroll_course_async(self, course_id: uuid.UUID, user: User):
        try:
            enroll = await self.db.scalar(
                select(CourseEnrollments).where(
                    CourseEnrollments.course_id == course_id,
                    CourseEnrollments.user_id == user.id,
                )
            )
            if enroll is None:
                return {
                    "message": "Nguoi dung chua dang ky khoa học",
                    "is_enroll": False,
                }
            return {"message": "Nguoi dung da dang ky khoa học", "is_enroll": True}
        except Exception as e:
            await self.db.commit()
            raise HTTPException(500, f"Lỗi server {e}")

    async def get_best_seller_courses(
        self,
        user_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        limit: int = 10,
        cursor: str | None = None,
        category_sv: CategoryService = Depends(CategoryService),
    ):
        try:
            # 1) Lấy thống kê GLOBAL cho cutoff 80%
            stats_stmt = select(
                Courses.views,
                Courses.total_enrolls,
                Courses.rating_avg,
            ).where(
                Courses.is_published.is_(True),
                Courses.approval_status == "approved",
            )
            stats = (await self.db.execute(stats_stmt)).mappings().all()
            if not stats:
                return {"items": [], "next_cursor": None}

            views_cutoff = np.percentile([s["views"] or 0 for s in stats], 80)
            enrolls_cutoff = np.percentile([s["total_enrolls"] or 0 for s in stats], 80)
            rating_cutoff = np.percentile(
                [float(s["rating_avg"] or 0) for s in stats], 80
            )

            # 2) Lấy category_ids nếu có slug, không có thì bỏ qua
            category_ids = None
            if category_slug:
                category_ids = await category_sv.get_all_subcategories(category_slug)

            # 3) Parse cursor
            last_value = None
            last_id = None
            if cursor:
                p = cursor.split("|")
                if len(p) == 2:
                    last_value = int(p[0])
                    last_id = p[1]

            # 4) Base query
            stmt = (
                select(Courses)
                .options(selectinload(Courses.instructor))
                .where(
                    Courses.is_published.is_(True),
                    Courses.approval_status == "approved",
                )
            )

            if category_ids:
                stmt = stmt.where(Courses.category_id.in_(category_ids))

            # Bỏ khóa học đã mua
            if user_id:
                purchased = select(CourseEnrollments.course_id).where(
                    CourseEnrollments.user_id == user_id,
                    CourseEnrollments.status == "active",
                )
                stmt = stmt.where(~Courses.id.in_(purchased))

            # Điều kiện cursor
            if last_value is not None:
                stmt = stmt.where(
                    (Courses.total_enrolls < last_value)
                    | ((Courses.total_enrolls == last_value) & (Courses.id < last_id))
                )

            stmt = stmt.order_by(
                Courses.total_enrolls.desc(),
                Courses.id.desc(),
            ).limit(limit + 1)

            rows = (await self.db.execute(stmt)).scalars().all()

            # 5) Next cursor - lấy từ item cuối được trả về
            has_more = len(rows) == limit + 1
            if has_more:
                rows = rows[:-1]  # Cắt bớt item thừa trước
            
            if has_more and rows:
                edge = rows[-1]  # Lấy item cuối ĐƯỢC TRẢ VỀ
                next_cursor = f"{int(edge.total_enrolls or 0)}|{edge.id}"
            else:
                next_cursor = None

            # 6) Build items + tags
            seven_days_ago = get_now() - timedelta(days=7)
            items = []

            for c in rows:
                tags = []
                if (c.views or 0) >= views_cutoff:
                    tags.append("thịnh hành")
                if (c.total_enrolls or 0) >= enrolls_cutoff:
                    tags.append("bán chạy nhất")
                if (c.rating_avg or 0) >= rating_cutoff:
                    tags.append("được yêu thích")

                created_at_stripped = strip_tz(c.created_at) if c.created_at else None
                if created_at_stripped and created_at_stripped >= seven_days_ago:
                    tags.append("mới ra mắt")

                items.append(
                    {
                        "id": str(c.id),
                        "title": c.title,
                        "thumbnail": c.thumbnail_url,
                        "base_price": c.base_price,
                        "views": int(c.views or 0),
                        "slug": c.slug,
                        "rating": float(c.rating_avg or 0),
                        "enrolls": int(c.total_enrolls or 0),
                        "tags": tags,
                        "instructor": (
                            {
                                "id": str(c.instructor.id),
                                "name": c.instructor.fullname,
                                "avatar": c.instructor.avatar,
                            }
                            if c.instructor
                            else None
                        ),
                    }
                )

            return {"items": items, "next_cursor": next_cursor}

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi best-seller: {e}")

    async def get_top_views_courses(
        self,
        user_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        limit: int = 10,
        cursor: str | None = None,
        category_sv: CategoryService = Depends(CategoryService),
    ):
        try:
            # 1) Lấy thống kê GLOBAL (cutoff 80%)
            stats_stmt = select(
                Courses.views,
                Courses.total_enrolls,
                Courses.rating_avg,
            ).where(
                Courses.is_published.is_(True),
                Courses.approval_status == "approved",
            )
            stats = (await self.db.execute(stats_stmt)).mappings().all()
            if not stats:
                return {"items": [], "next_cursor": None}

            # Cutoff
            views_cutoff = np.percentile([s["views"] or 0 for s in stats], 80)
            enrolls_cutoff = np.percentile([s["total_enrolls"] or 0 for s in stats], 80)
            rating_cutoff = np.percentile(
                [float(s["rating_avg"] or 0) for s in stats], 80
            )

            # 2) Categories filter
            category_ids = None
            if category_slug:
                category_ids = await category_sv.get_all_subcategories(category_slug)

            # 3) Parse cursor: view|id
            last_views = None
            last_id = None
            if cursor:
                p = cursor.split("|")
                if len(p) == 2:
                    last_views = int(p[0])
                    last_id = p[1]

            # 4) Base query
            stmt = (
                select(Courses)
                .options(selectinload(Courses.instructor))
                .where(
                    Courses.is_published.is_(True),
                    Courses.approval_status == "approved",
                )
            )

            if category_ids:
                stmt = stmt.where(Courses.category_id.in_(category_ids))

            # Bỏ khóa học đã mua
            if user_id:
                purchased = select(CourseEnrollments.course_id).where(
                    CourseEnrollments.user_id == user_id,
                    CourseEnrollments.status == "active",
                )
                stmt = stmt.where(~Courses.id.in_(purchased))

            # 5) Cursor condition (theo views)
            if last_views is not None:
                stmt = stmt.where(
                    (Courses.views < last_views)
                    | ((Courses.views == last_views) & (Courses.id < last_id))
                )

            # 6) Order by views desc
            stmt = stmt.order_by(
                Courses.views.desc(),
                Courses.id.desc(),
            ).limit(limit + 1)

            rows = (await self.db.execute(stmt)).scalars().all()

            # 7) Next cursor - lấy từ item cuối được trả về
            has_more = len(rows) == limit + 1
            if has_more:
                rows = rows[:-1]  # Cắt bớt item thừa trước
            
            if has_more and rows:
                edge = rows[-1]  # Lấy item cuối ĐƯỢC TRẢ VỀ
                next_cursor = f"{int(edge.views or 0)}|{edge.id}"
            else:
                next_cursor = None

            # 8) Build items + tags
            seven_days_ago = get_now() - timedelta(days=7)
            items = []

            for c in rows:
                tags = []
                if (c.views or 0) >= views_cutoff:
                    tags.append("thịnh hành")
                if (c.total_enrolls or 0) >= enrolls_cutoff:
                    tags.append("bán chạy nhất")
                if (c.rating_avg or 0) >= rating_cutoff:
                    tags.append("được yêu thích")

                created_at_stripped = strip_tz(c.created_at) if c.created_at else None
                if created_at_stripped and created_at_stripped >= seven_days_ago:
                    tags.append("mới ra mắt")

                items.append(
                    {
                        "id": str(c.id),
                        "title": c.title,
                        "thumbnail": c.thumbnail_url,
                        "base_price": c.base_price,
                        "views": int(c.views or 0),
                        "slug": c.slug,
                        "rating": float(c.rating_avg or 0),
                        "enrolls": int(c.total_enrolls or 0),
                        "tags": tags,
                        "instructor": (
                            {
                                "id": str(c.instructor.id),
                                "name": c.instructor.fullname,
                                "avatar": c.instructor.avatar,
                            }
                            if c.instructor
                            else None
                        ),
                    }
                )

            return {"items": items, "next_cursor": next_cursor}

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi top-views: {e}")

    async def get_newest_courses(
        self,
        category_slug: str | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 10,
        cursor: str | None = None,
        category_sv: CategoryService = Depends(CategoryService),
    ):
        try:
            # 1) GLOBAL cutoff
            stats_stmt = select(
                Courses.views,
                Courses.total_enrolls,
                Courses.rating_avg,
            ).where(
                Courses.is_published.is_(True),
                Courses.approval_status == "approved",
            )
            stats = (await self.db.execute(stats_stmt)).mappings().all()
            if not stats:
                return {"items": [], "next_cursor": None}

            views_cutoff = np.percentile([s["views"] or 0 for s in stats], 80)
            enrolls_cutoff = np.percentile([s["total_enrolls"] or 0 for s in stats], 80)
            rating_cutoff = np.percentile(
                [float(s["rating_avg"] or 0) for s in stats], 80
            )

            # 2) Category filter (optional)
            category_ids = None
            if category_slug:
                category_ids = await category_sv.get_all_subcategories(category_slug)

            # 3) Cursor parse
            last_date = None
            last_id = None
            if cursor:
                p = cursor.split("|")
                if len(p) == 2:
                    last_date = datetime.fromisoformat(p[0])
                    last_id = p[1]

            # 4) Base query
            stmt = (
                select(Courses)
                .options(selectinload(Courses.instructor))
                .where(
                    Courses.is_published.is_(True),
                    Courses.approval_status == "approved",
                )
            )

            if category_ids:
                stmt = stmt.where(Courses.category_id.in_(category_ids))

            if user_id:
                purchased = select(CourseEnrollments.course_id).where(
                    CourseEnrollments.user_id == user_id,
                    CourseEnrollments.status == "active",
                )
                stmt = stmt.where(~Courses.id.in_(purchased))

            if last_date:
                stmt = stmt.where(
                    (Courses.created_at < last_date)
                    | ((Courses.created_at == last_date) & (Courses.id < last_id))
                )

            stmt = stmt.order_by(
                Courses.created_at.desc(),
                Courses.id.desc(),
            ).limit(limit + 1)

            rows = (await self.db.execute(stmt)).scalars().all()

            # 5) Next cursor - lấy từ item cuối được trả về
            has_more = len(rows) == limit + 1
            if has_more:
                rows = rows[:-1]  # Cắt bớt item thừa trước
            
            if has_more and rows:
                edge = rows[-1]  # Lấy item cuối ĐƯỢC TRẢ VỀ
                next_cursor = f"{edge.created_at.isoformat()}|{edge.id}"
            else:
                next_cursor = None

            # 6) Build items + tags
            seven_days_ago = get_now() - timedelta(days=7)
            items = []

            for c in rows:
                tags = []
                if (c.views or 0) >= views_cutoff:
                    tags.append("thịnh hành")
                if (c.total_enrolls or 0) >= enrolls_cutoff:
                    tags.append("bán chạy nhất")
                if (c.rating_avg or 0) >= rating_cutoff:
                    tags.append("được yêu thích")

                created_at_stripped = strip_tz(c.created_at) if c.created_at else None
                if created_at_stripped and created_at_stripped >= seven_days_ago:
                    tags.append("mới ra mắt")

                items.append(
                    {
                        "id": str(c.id),
                        "title": c.title,
                        "thumbnail": c.thumbnail_url,
                        "base_price": c.base_price,
                        "views": int(c.views or 0),
                        "slug": c.slug,
                        "rating": float(c.rating_avg or 0),
                        "enrolls": int(c.total_enrolls or 0),
                        "tags": tags,
                        "instructor": (
                            {
                                "id": str(c.instructor.id),
                                "name": c.instructor.fullname,
                                "avatar": c.instructor.avatar,
                            }
                            if c.instructor
                            else None
                        ),
                    }
                )

            return {"items": items, "next_cursor": next_cursor}

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi newest: {e}")

    async def get_top_rated_courses(
        self,
        user_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        limit: int = 10,
        cursor: str | None = None,
        category_sv: CategoryService = Depends(CategoryService),
    ):
        try:
            # 1) GLOBAL cutoff
            stats_stmt = select(
                Courses.views,
                Courses.total_enrolls,
                Courses.rating_avg,
            ).where(
                Courses.is_published.is_(True),
                Courses.approval_status == "approved",
            )
            stats = (await self.db.execute(stats_stmt)).mappings().all()
            if not stats:
                return {"items": [], "next_cursor": None}

            views_cutoff = np.percentile([s["views"] or 0 for s in stats], 80)
            enrolls_cutoff = np.percentile([s["total_enrolls"] or 0 for s in stats], 80)
            rating_cutoff = np.percentile(
                [float(s["rating_avg"] or 0) for s in stats], 80
            )

            # 2) Category (optional)
            category_ids = None
            if category_slug:
                category_ids = await category_sv.get_all_subcategories(category_slug)

            # 3) Cursor
            last_rating = None
            last_id = None
            if cursor:
                p = cursor.split("|")
                if len(p) == 2:
                    last_rating = float(p[0])
                    last_id = p[1]

            # 4) Base query - lấy khóa học được đánh giá cao nhất, không lọc theo views
            stmt = (
                select(Courses)
                .options(selectinload(Courses.instructor))
                .where(
                    Courses.is_published.is_(True),
                    Courses.approval_status == "approved",
                    Courses.rating_count > 0,  # chỉ lấy khóa đã có đánh giá
                )
            )

            if category_ids:
                stmt = stmt.where(Courses.category_id.in_(category_ids))

            if user_id:
                purchased = select(CourseEnrollments.course_id).where(
                    CourseEnrollments.user_id == user_id,
                    CourseEnrollments.status == "active",
                )
                stmt = stmt.where(~Courses.id.in_(purchased))

            if last_rating is not None:
                stmt = stmt.where(
                    (Courses.rating_avg < last_rating)
                    | ((Courses.rating_avg == last_rating) & (Courses.id < last_id))
                )

            stmt = stmt.order_by(
                Courses.rating_avg.desc(),
                Courses.id.desc(),
            ).limit(limit + 1)

            rows = (await self.db.execute(stmt)).scalars().all()

            # 5) Next cursor - lấy từ item cuối được trả về
            has_more = len(rows) == limit + 1
            if has_more:
                rows = rows[:-1]  # Cắt bớt item thừa trước
            
            if has_more and rows:
                edge = rows[-1]  # Lấy item cuối ĐƯỢC TRẢ VỀ
                next_cursor = f"{float(edge.rating_avg or 0)}|{edge.id}"
            else:
                next_cursor = None

            # 6) Build result
            seven_days_ago = get_now() - timedelta(days=7)
            items = []

            for c in rows:
                tags = []
                if (c.views or 0) >= views_cutoff:
                    tags.append("thịnh hành")
                if (c.total_enrolls or 0) >= enrolls_cutoff:
                    tags.append("bán chạy nhất")
                if (c.rating_avg or 0) >= rating_cutoff:
                    tags.append("được yêu thích")

                created_at_stripped = strip_tz(c.created_at) if c.created_at else None
                if created_at_stripped and created_at_stripped >= seven_days_ago:
                    tags.append("mới ra mắt")

                items.append(
                    {
                        "id": str(c.id),
                        "title": c.title,
                        "thumbnail": c.thumbnail_url,
                        "base_price": c.base_price,
                        "views": int(c.views or 0),
                        "slug": c.slug,
                        "rating_avg": float(c.rating_avg or 0),
                        "enrolls": int(c.total_enrolls or 0),
                        "tags": tags,
                        "instructor": (
                            {
                                "id": str(c.instructor.id),
                                "name": c.instructor.fullname,
                                "avatar": c.instructor.avatar,
                            }
                            if c.instructor
                            else None
                        ),
                    }
                )

            return {"items": items, "next_cursor": next_cursor}

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi top-rated: {e}")

    async def get_recommended_top20(self, user_id: uuid.UUID):
        try:
            stmt = select(
                literal_column("course_id"),
                literal_column("course_title"),
                literal_column("course_thumbnail"),
                literal_column("instructor_id"),
                literal_column("instructor_name"),
                literal_column("instructor_avatar"),
                literal_column("course_slug"),
                literal_column("similarity"),
            ).select_from(
                func.fn_recommend_top20(cast(literal_column(f"'{user_id}'"), UUID))
            )

            rows = (await self.db.execute(stmt)).mappings().all()

            return {
                "items": [
                    {
                        "id": str(r["course_id"]),
                        "title": r["course_title"],
                        "thumbnail": r["course_thumbnail"],
                        "slug": r["course_slug"],
                        "instructor": {
                            "id": str(r["instructor_id"]),
                            "name": r["instructor_name"],
                            "avatar": r["instructor_avatar"],
                        },
                        "similarity": float(r["similarity"]),
                    }
                    for r in rows
                ]
            }

        except Exception as e:
            await self.db.rollback()
            raise e
