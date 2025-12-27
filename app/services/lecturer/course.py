# app/services/lecturer/course_service.py
import csv
import io
import math
import uuid
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, HTTPException, UploadFile
from slugify import slugify
from sqlalchemy import asc, case, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import EmbeddingService, get_embedding_service
from app.db.models.database import (
    Categories,
    CourseEnrollments,
    Courses,
    CourseSections,
    Discounts,
    InstructorEarnings,
    LessonProgress,
    Lessons,
    PurchaseItems,
    Topics,
    Transactions,
    User,
)
from app.db.sesson import AsyncSessionLocal, get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import now_tzinfo, to_utc_naive
from app.schemas.lecturer.courses import CreateCourse, UpdateCourse
from app.services.shares.google_driver import (
    GoogleDriveAsyncService,
    get_google_drive_service,
)


class CourseService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive: GoogleDriveAsyncService = Depends(get_google_drive_service),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db
        self.google_drive = google_drive
        self.embedding = embedding

    # ======================================================
    # 🧩 Tạo khóa học mới — chạy nhanh, mọi thứ khác chạy nền
    # ======================================================
    async def create_course_async(
        self, lecturer: User, schema: CreateCourse, background_tasks: BackgroundTasks
    ):
        """
        ✅ Tạo khóa học mới an toàn:
        - Kiểm tra dữ liệu hợp lệ
        - Lưu DB ngay
        - Task nền: upload thumbnail + tạo embedding
        """
        try:
            # 1️⃣ Kiểm tra giảng viên hợp lệ
            if not lecturer or not lecturer.id:
                raise HTTPException(401, "❌ Không xác định được giảng viên")

            # 2️⃣ Kiểm tra category tồn tại
            category_exists = await self.db.scalar(
                select(Categories.id).where(Categories.id == schema.category_id)
            )
            if not category_exists:
                raise HTTPException(400, "❌ Category không tồn tại")

            # 3️⃣ Nếu có topic_id → kiểm tra topic tồn tại và cùng category
            if schema.topic_id:
                topic = await self.db.scalar(
                    select(Topics).where(Topics.id == schema.topic_id)
                )
                if not topic:
                    raise HTTPException(400, "❌ Topic không tồn tại")
                if topic.category_id != schema.category_id:
                    raise HTTPException(
                        400, f"⚠️ Topic '{topic.name}' không thuộc category này"
                    )

            # 4️⃣ Validate dữ liệu cơ bản
            if not schema.title or not schema.title.strip():
                raise HTTPException(400, "❌ Tiêu đề khóa học không được để trống")

            if schema.base_price is not None and schema.base_price < 0:
                raise HTTPException(400, "⚠️ Giá không hợp lệ (phải >= 0)")

            base_slug = slugify(schema.title)
            slug = base_slug
            i = 1
            while await self.db.scalar(select(Courses.id).where(Courses.slug == slug)):
                slug = f"{base_slug}-{i}"
                i += 1

            new_course = Courses(
                **schema.model_dump(exclude={"thumbnail_file"}),
                instructor_id=lecturer.id,
                slug=slug,
                created_at=await to_utc_naive(get_now()),
                updated_at=await to_utc_naive(get_now()),
            )

            # 6️⃣ Lưu DB ngay để có course_id
            self.db.add(new_course)
            await self.db.flush()

            # ✅ CẬP NHẬT USER.COURSE_COUNT CHO GIẢNG VIÊN
            lecturer.course_count = (lecturer.course_count or 0) + 1

            await self.db.commit()
            await self.db.refresh(new_course)
            background_tasks.add_task(self._process_embedding_and_search, new_course.id)
            return {
                "message": "✅ Tạo khóa học thành công",
                "course_id": str(new_course.id),
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"❌ Lỗi khi tạo khóa học: {e}")

    # ======================================================
    # 🧠 Task nền: xử lý embedding + tsvector
    # ======================================================
    @staticmethod
    async def _process_embedding_and_search(course_id: uuid.UUID):
        async with AsyncSessionLocal() as db:
            try:
                course = await db.get(Courses, course_id)
                if not course:
                    print(f"⚠️ Không tìm thấy khóa học {course_id}")
                    return

                text_for_embed = "\n".join(
                    [
                        course.title or "",
                        course.description or "",
                        " ".join(course.outcomes or []),
                        " ".join(course.requirements or []),
                        " ".join(course.target_audience or []),
                    ]
                )

                embed_service = await get_embedding_service()
                vector = await embed_service.embed_google_normalized(text_for_embed)

                text_search = " ".join(
                    [
                        course.title or "",
                        course.subtitle or "",
                        course.description or "",
                        " ".join(course.outcomes or []),
                        " ".join(course.requirements or []),
                        " ".join(course.target_audience or []),
                    ]
                )

                course.embedding = vector
                course.search_tsv = func.to_tsvector("simple", text_search)
                course.embedding_updated_at = await to_utc_naive(get_now())
                course.updated_at = await to_utc_naive(get_now())

                await db.commit()
                print(f"✅ [{course_id}] Embedding và full-text đã hoàn tất")

            except Exception as e:
                await db.rollback()
                print(f"❌ Lỗi xử lý nền cho khóa học {course_id}: {e}")

    async def upload_thumbnail_async(self, course_id: str, file: UploadFile):
        """
        ✅ Upload ảnh thumbnail lên Google Drive, lưu URL public vào DB
        """
        try:
            # kiểm tra course tồn tại
            course = await self.db.get(Courses, course_id)
            if not course:
                raise HTTPException(404, "Không tìm thấy khóa học")

            filename = f"{uuid4().hex}_{file.filename}"
            content = await file.read()

            uploaded = await self.google_drive.upload_file(
                path_parts=["courses", str(course_id), "thumbnails"],
                file_name=filename,
                content=content,
            )

            file_id = uploaded.get("id")
            if not file_id:
                raise HTTPException(500, "Không nhận được file_id từ Google Drive API")

            links = await self.google_drive.create_share_link(file_id)
            view_link = links["view_link"]

            await self.db.execute(
                update(Courses)
                .where(Courses.id == course_id)
                .values(thumbnail_url=view_link)
            )
            await self.db.commit()

            return {
                "message": "✅ Upload thumbnail thành công",
                "thumbnail_url": view_link,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"❌ Lỗi upload thumbnail: {e}")

    # ======================================================
    # 📊 Lấy danh sách khóa học theo giảng viên
    # ======================================================
    async def get_courses_by_lecturer_async(
        self,
        lecturer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        sort_by: str | None = "revenue",
        sort_dir: str | None = "desc",
        search: str | None = None,
        approval_status: str | None = None,
    ):
        lecturer = await self.db.scalar(select(User).where(User.id == lecturer_id))
        if not lecturer:
            raise HTTPException(404, "Không tìm thấy giảng viên")

        rev_subq = (
            select(
                Transactions.course_id.label("course_id"),
                func.sum(Transactions.amount).label("total_revenue"),
            )
            .where(Transactions.status == "success")
            .group_by(Transactions.course_id)
            .subquery()
        )
        rev_col = rev_subq.c.total_revenue

        stmt = (
            select(Courses, func.coalesce(rev_col, 0).label("total_revenue"))
            .join(rev_subq, rev_subq.c.course_id == Courses.id, isouter=True)
            .where(Courses.instructor_id == lecturer_id)
            .options(
                selectinload(Courses.category),
                selectinload(Courses.course_sections).selectinload(
                    CourseSections.lessons
                ),
            )
        )

        if search:
            stmt = stmt.where(Courses.title.ilike(f"%{search}%"))
        if approval_status:
            stmt = stmt.where(Courses.approval_status == approval_status)

        is_desc = (sort_dir or "desc").lower() != "asc"
        approval_order = case(
            (Courses.approval_status == "pending", 0),
            (Courses.approval_status == "rejected", 1),
            (Courses.approval_status == "approved", 2),
            else_=3,
        )
        sort_keys = {
            "revenue": (rev_col,),
            "created_at": (Courses.created_at,),
            "views": (Courses.views,),
            "enrolls": (Courses.total_enrolls,),
            "rating": (Courses.rating_avg,),
            "approval": (approval_order,),
        }
        key_cols = sort_keys.get((sort_by or "revenue"), (rev_col,))

        def apply_dir(col):
            return desc(col).nullslast() if is_desc else asc(col).nullslast()

        order_clauses = [apply_dir(c) for c in key_cols]
        order_clauses += [desc(Courses.created_at), desc(Courses.id)]
        stmt = stmt.order_by(*order_clauses)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        res = await self.db.execute(stmt)
        rows = res.mappings().all()

        total_count = (
            await self.db.scalar(
                select(func.count()).select_from(
                    select(Courses.id)
                    .where(Courses.instructor_id == lecturer_id)
                    .subquery()
                )
            )
            or 0
        )

        if not rows:
            return {
                "status": "empty",
                "message": "Giảng viên chưa có khóa học nào.",
                "courses": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 0,
                },
            }

        data = []
        for r in rows:
            c = r["Courses"]
            revenue = float(r["total_revenue"] or 0)
            sections_count = len(c.course_sections)
            lessons_count = sum(len(s.lessons) for s in c.course_sections)
            data.append(
                {
                    "id": str(c.id),
                    "title": c.title,
                    "slug": c.slug,
                    "thumbnail_url": c.thumbnail_url,
                    "rating_avg": float(c.rating_avg or 0),
                    "views": c.views or 0,
                    "base_price": float(c.base_price or 0),
                    "total_enrolls": c.total_enrolls or 0,
                    "revenue": revenue,
                    "approval_status": c.approval_status,
                    "approval_note": c.approval_note,
                    "approved_by": str(c.approved_by) if c.approved_by else None,
                    "approved_at": c.approved_at,
                    "review_round": c.review_round,
                    "is_published": c.is_published,
                    "sections_count": sections_count,
                    "lessons_count": lessons_count,
                    "category": (
                        {
                            "id": str(c.category.id),
                            "name": c.category.name,
                            "slug": c.category.slug,
                        }
                        if c.category
                        else None
                    ),
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
            )

        return {
            "status": "ok",
            "lecturer": {
                "id": str(lecturer.id),
                "fullname": lecturer.fullname,
                "avatar": lecturer.avatar,
            },
            "courses": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "total_pages": math.ceil(total_count / page_size) if page_size else 1,
            },
        }

    async def get_course_detail_async(self, course_id: str, lecturer_id: uuid.UUID):
        """
        ✅ Lấy chi tiết 1 khóa học (dùng cho trang chỉnh sửa)
        """
        course = await self.db.scalar(
            select(Courses)
            .options(
                selectinload(Courses.category),
                selectinload(Courses.topic),
                selectinload(Courses.course_sections).selectinload(
                    CourseSections.lessons
                ),
            )
            .where(Courses.id == course_id, Courses.instructor_id == lecturer_id)
        )

        if not course:
            raise HTTPException(status_code=404, detail="❌ Không tìm thấy khóa học")

        return {
            "id": str(course.id),
            "title": course.title,
            "slug": course.slug,
            "subtitle": course.subtitle,
            "description": course.description,
            "level": course.level,
            "language": course.language,
            "is_published": course.is_published,
            "is_lock_lesson": course.is_lock_lesson,
            "approval_status": course.approval_status,
            "approval_note": course.approval_note,
            "review_round": course.review_round,
            "base_price": float(course.base_price or 0),
            "currency": course.currency,
            "thumbnail_url": course.thumbnail_url,
            "outcomes": course.outcomes or [],
            "requirements": course.requirements or [],
            "target_audience": course.target_audience or [],
            "category": (
                {
                    "id": str(course.category.id),
                    "name": course.category.name,
                    "slug": course.category.slug,
                }
                if course.category
                else None
            ),
            "topic": (
                {
                    "id": str(course.topic.id),
                    "name": course.topic.name,
                }
                if course.topic
                else None
            ),
            "created_at": course.created_at,
            "updated_at": course.updated_at,
        }

    async def update_course_async(
        self,
        course_id: str,
        lecturer_id: uuid.UUID,
        schema: UpdateCourse,
        background_tasks: BackgroundTasks,
    ):
        """
        ✅ Cập nhật khóa học:
        - Kiểm tra category/topic hợp lệ
        - Cập nhật thông tin cơ bản
        - Nếu thay đổi title/description → cập nhật embedding nền
        """
        # 1️⃣ Kiểm tra khóa học tồn tại
        course = await self.db.scalar(
            select(Courses).where(
                Courses.id == course_id, Courses.instructor_id == lecturer_id
            )
        )
        if not course:
            raise HTTPException(
                404, "❌ Không tìm thấy khóa học hoặc không có quyền truy cập"
            )

        # 2️⃣ Kiểm tra category
        if schema.category_id:
            category = await self.db.get(Categories, schema.category_id)
            if not category:
                raise HTTPException(400, "❌ Category không tồn tại")

        # 3️⃣ Kiểm tra topic (nếu có)
        topic = None
        if schema.topic_id:
            topic = await self.db.get(Topics, schema.topic_id)
            if not topic:
                raise HTTPException(400, "❌ Topic không tồn tại")
            if topic.category_id != schema.category_id:
                raise HTTPException(400, "⚠️ Topic không thuộc category này")

        # 4️⃣ Kiểm tra giá
        if schema.base_price is not None and schema.base_price < 0:
            raise HTTPException(400, "⚠️ Giá khóa học không hợp lệ (phải >= 0)")

        # 5️⃣ Xác định xem có cần làm lại embedding không
        re_embed = (schema.title and schema.title != course.title) or (
            schema.description and schema.description != course.description
        )

        # 6️⃣ Cập nhật thông tin
        update_data = schema.model_dump(exclude_unset=True)
        update_data["updated_at"] = await to_utc_naive(get_now())

        await self.db.execute(
            update(Courses).where(Courses.id == course_id).values(**update_data)
        )
        await self.db.commit()

        # 7️⃣ Làm lại embedding nền nếu cần
        if re_embed:
            background_tasks.add_task(
                CourseService._rebuild_embedding_task,
                course_id,
            )

        # 8️⃣ Lấy lại khóa học sau khi update
        updated = await self.db.scalar(
            select(Courses)
            .options(
                selectinload(Courses.category),
                selectinload(Courses.topic),
            )
            .where(Courses.id == course_id)
        )

        return {
            "id": str(updated.id),
            "title": updated.title,
            "slug": updated.slug,
            "subtitle": updated.subtitle,
            "description": updated.description,
            "level": updated.level,
            "language": updated.language,
            "is_published": updated.is_published,
            "approval_status": updated.approval_status,
            "approval_note": updated.approval_note,
            "base_price": float(updated.base_price or 0),
            "currency": updated.currency,
            "thumbnail_url": updated.thumbnail_url,
            "outcomes": updated.outcomes or [],
            "requirements": updated.requirements or [],
            "target_audience": updated.target_audience or [],
            "category": (
                {
                    "id": str(updated.category.id),
                    "name": updated.category.name,
                    "slug": updated.category.slug,
                }
                if updated.category
                else None
            ),
            "topic": (
                {
                    "id": str(updated.topic.id),
                    "name": updated.topic.name,
                }
                if updated.topic
                else None
            ),
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }

    # ========================
    # 🧠 Task nền làm lại embedding
    # ========================
    @staticmethod
    async def _rebuild_embedding_task(course_id: str):
        async with AsyncSessionLocal() as db:
            try:
                course = await db.get(Courses, course_id)
                if not course:
                    print(f"⚠️ Không tìm thấy khóa học {course_id}")
                    return

                text_for_embed = "\n".join(
                    [
                        course.title or "",
                        course.description or "",
                        " ".join(course.outcomes or []),
                        " ".join(course.requirements or []),
                        " ".join(course.target_audience or []),
                    ]
                )

                embed_service = await get_embedding_service()
                vector = await embed_service.embed_google_normalized(text_for_embed)

                await db.execute(
                    update(Courses)
                    .where(Courses.id == course_id)
                    .values(
                        embedding=vector,
                        embedding_updated_at=await to_utc_naive(get_now()),
                        updated_at=await to_utc_naive(get_now()),
                    )
                )
                await db.commit()
                print(f"✅ [{course_id}] Làm lại embedding thành công")

            except Exception as e:
                await db.rollback()
                print(f"❌ Lỗi làm lại embedding cho {course_id}: {e}")

    async def delete_course_async(self, course_id: uuid.UUID, lecturer_id: uuid.UUID):
        # 1️⃣ Kiểm tra khóa học tồn tại
        course = await self.db.scalar(select(Courses).where(Courses.id == course_id))
        if not course:
            raise HTTPException(status_code=404, detail="Không tìm thấy khóa học")

        if course.instructor_id != lecturer_id:
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền xóa khóa học này",
            )

        if course.total_enrolls and course.total_enrolls > 0:
            raise HTTPException(
                status_code=400,
                detail="❌ Khóa học đã có học viên đăng ký, không thể xóa.",
            )

        # 3️⃣ Cho phép xóa + CẬP NHẬT THỐNG KÊ
        # ✅ GIẢM COURSE_COUNT CHO LECTURER
        lecturer = await self.db.scalar(
            select(User).where(User.id == lecturer_id)
        )
        if lecturer:
            lecturer.course_count = max((lecturer.course_count or 1) - 1, 0)

        await self.db.execute(delete(Courses).where(Courses.id == course_id))
        await self.db.commit()

        return {"message": "✅ Đã xóa khóa học thành công"}

    async def get_courses_for_discount_async(
        self,
        lecturer: User,
        search: str | None = None,
        approval_status: str | None = None,
        is_published: bool | None = None,
    ):
        # Verify lecturer

        # Base query: lấy tất cả khóa học của giảng viên
        stmt = (
            select(
                Courses.id,
                Courses.title,
                Courses.thumbnail_url,
                Courses.base_price,
                Courses.approval_status,
                Courses.is_published,
                Categories.id.label("category_id"),
                Categories.name.label("category_name"),
            )
            .join(Categories, Categories.id == Courses.category_id, isouter=True)
            .where(Courses.instructor_id == lecturer.id)
        )

        # search
        if search:
            stmt = stmt.where(Courses.title.ilike(f"%{search}%"))

        # filter theo duyệt
        if approval_status:
            stmt = stmt.where(Courses.approval_status == approval_status)

        # filter publish
        if is_published is not None:
            stmt = stmt.where(Courses.is_published.is_(is_published))

        # order mới nhất lên trước
        stmt = stmt.order_by(Courses.created_at.desc())

        # execute
        rows = (await self.db.execute(stmt)).all()

        courses = [
            {
                "id": str(r.id),
                "title": r.title,
                "thumbnail_url": r.thumbnail_url,
                "base_price": float(r.base_price or 0),
                "approval_status": r.approval_status,
                "is_published": r.is_published,
                "category": {
                    "id": str(r.category_id) if r.category_id else None,
                    "name": r.category_name,
                },
            }
            for r in rows
        ]

        return {
            "courses": courses,
            "count": len(courses),
        }

    async def get_course_student_detail_async(
        self,
        course_id: uuid.UUID,
        student_id: uuid.UUID,
        instructor_id: uuid.UUID,
    ):
        """
        Chi tiết học viên FULL:
        - giá mua, discount, ngày mua
        - tiến độ %, completed_at
        - bài đang học
        - last activity
        - timeline bài học
        """

        # ============================
        # 1) CHECK COURSE
        # ============================
        course = await self.db.scalar(select(Courses).where(Courses.id == course_id))
        if not course:
            raise HTTPException(404, "Khóa học không tồn tại.")

        if course.instructor_id != instructor_id:
            raise HTTPException(403, "Bạn không có quyền xem học viên này.")

        # ============================
        # 2) CHECK STUDENT ENROLL
        # ============================
        enroll = await self.db.scalar(
            select(CourseEnrollments).where(
                CourseEnrollments.course_id == course_id,
                CourseEnrollments.user_id == student_id,
            )
        )
        if not enroll:
            raise HTTPException(404, "Học viên chưa đăng ký khóa học này.")

        # ============================
        # 3) STUDENT INFO
        # ============================
        student = await self.db.scalar(select(User).where(User.id == student_id))

        # ============================
        # 4) PURCHASE INFO
        # ============================
        purchase_item = await self.db.scalar(
            select(PurchaseItems).where(
                PurchaseItems.course_id == course_id,
                PurchaseItems.user_id == student_id,
            )
        )

        discount_code = None
        price_paid = 0
        original_price = None
        discount_amount = None
        purchase_time = None

        if purchase_item:
            price_paid = float(purchase_item.discounted_price or 0)
            original_price = float(purchase_item.original_price or 0)
            discount_amount = float(purchase_item.discount_amount or 0)
            purchase_time = purchase_item.created_at.isoformat()
            if purchase_item.discount_id:
                # lấy mã giảm giá
                disc = await self.db.scalar(
                    select(Discounts).where(Discounts.id == purchase_item.discount_id)
                )
                discount_code = disc.discount_code if disc else None

        # ============================
        # 5) LẤY TOÀN BỘ BÀI HỌC
        # ============================
        lessons = (
            (
                await self.db.execute(
                    select(Lessons)
                    .where(Lessons.course_id == course_id)
                    .order_by(Lessons.position.asc())
                )
            )
            .scalars()
            .all()
        )
        lesson_ids = [l.id for l in lessons]

        total_lessons = len(lessons)

        # ============================
        # 6) LẤY PROGRESS
        # ============================
        progresses = (
            (
                await self.db.execute(
                    select(LessonProgress).where(
                        LessonProgress.user_id == student_id,
                        LessonProgress.lesson_id.in_(lesson_ids),
                    )
                )
            )
            .scalars()
            .all()
        )

        progress_map = {p.lesson_id: p for p in progresses}

        completed_count = sum(1 for p in progresses if p.is_completed)

        progress_percent = (
            completed_count / total_lessons * 100 if total_lessons > 0 else 0
        )

        # ngày hoàn thành khóa (bài cuối completed)
        course_completed_at = None
        if progress_percent == 100:
            course_completed_at = max(
                (p.completed_at for p in progresses if p.completed_at), default=None
            )
            if course_completed_at:
                course_completed_at = course_completed_at.isoformat()

        # ============================
        # 7) XÁC ĐỊNH BÀI ĐANG HỌC
        # ============================
        current_lesson = None
        for lesson in lessons:
            if (
                lesson.id not in progress_map
                or not progress_map[lesson.id].is_completed
            ):
                current_lesson = {
                    "lesson_id": str(lesson.id),
                    "title": lesson.title,
                    "position": lesson.position,
                }
                break

        # ============================
        # 8) FORMAT DETAIL LIST
        # ============================
        lesson_detail_list = []
        last_activity = None

        for lesson in lessons:
            p = progress_map.get(lesson.id)

            if p and p.completed_at:
                if last_activity is None or p.completed_at > last_activity:
                    last_activity = p.completed_at

            lesson_detail_list.append(
                {
                    "lesson_id": str(lesson.id),
                    "title": lesson.title,
                    "type": lesson.lesson_type,
                    "position": lesson.position,
                    "is_completed": True if p and p.is_completed else False,
                    "completed_at": (
                        p.completed_at.isoformat() if p and p.completed_at else None
                    ),
                }
            )

        if not last_activity:
            last_activity = enroll.last_accessed

        last_activity_iso = last_activity.isoformat() if last_activity else None

        # ============================
        # 9) RETURN
        # ============================
        return {
            "course": {
                "id": str(course.id),
                "title": course.title,
                "total_lessons": total_lessons,
            },
            "student": {
                "id": str(student.id),
                "fullname": student.fullname,
                "email": student.email,
                "avatar": student.avatar,
                "enrolled_at": (
                    enroll.enrolled_at.isoformat() if enroll.enrolled_at else None
                ),
                "last_accessed": (
                    enroll.last_accessed.isoformat() if enroll.last_accessed else None
                ),
                "last_activity": last_activity_iso,
            },
            "purchase": {
                "price_paid": price_paid,
                "original_price": original_price,
                "discount_amount": discount_amount,
                "discount_code": discount_code,
                "purchase_time": purchase_time,
            },
            "progress": {
                "completed_lessons": completed_count,
                "total_lessons": total_lessons,
                "progress_percent": round(progress_percent, 2),
                "course_completed_at": course_completed_at,
                "current_lesson": current_lesson,
            },
            "lessons": lesson_detail_list,
        }

    async def get_course_students_list_async(
        self,
        course_id: uuid.UUID,
        instructor_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        min_progress: float | None = None,
        max_progress: float | None = None,
        status: str | None = None,  # not_started / learning / almost / completed
        sort_by: str = "enrolled_at",
        order_dir: str = "desc",
    ):
        """
        FULL Student Analytics:
        - fullname, email, avatar
        - giá mua
        - tiến độ %
        - thời điểm hoạt động cuối
        - lọc tiến độ, tìm kiếm, phân trang
        - sort theo: progress, price, enrolled_at, last_activity
        """

        # ========== 1) CHECK COURSE OWNERSHIP ==========
        course = await self.db.scalar(select(Courses).where(Courses.id == course_id))
        if not course:
            raise HTTPException(404, "Khóa học không tồn tại.")

        if course.instructor_id != instructor_id:
            raise HTTPException(403, "Bạn không có quyền xem học viên của khóa này.")

        # ========== 2) COUNT LESSONS ==========
        total_lessons = (
            await self.db.scalar(
                select(func.count(Lessons.id)).where(Lessons.course_id == course_id)
            )
            or 0
        )

        # ========== 3) BASE QUERY ==========
        stmt = (
            select(
                User.id.label("user_id"),
                User.fullname,
                User.email,
                User.avatar,
                CourseEnrollments.enrolled_at,
                CourseEnrollments.last_accessed,
                # tổng số bài đã hoàn thành
                func.coalesce(
                    func.sum(
                        case(
                            (LessonProgress.is_completed.is_(True), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed_lessons"),
                func.max(LessonProgress.completed_at).label("last_completed_at"),
                func.min(PurchaseItems.discounted_price).label("price_paid"),
            )
            .join(CourseEnrollments, CourseEnrollments.user_id == User.id)
            .outerjoin(
                LessonProgress,
                (LessonProgress.user_id == User.id)
                & (LessonProgress.course_id == course_id),
            )
            .outerjoin(
                PurchaseItems,
                (PurchaseItems.user_id == User.id)
                & (PurchaseItems.course_id == course_id),
            )
            .where(CourseEnrollments.course_id == course_id)
            .where(User.id != instructor_id)
            .group_by(
                User.id,
                User.fullname,
                User.email,
                User.avatar,
                CourseEnrollments.enrolled_at,
                CourseEnrollments.last_accessed,
            )
        )

        # ========== 4) SEARCH ==========
        if search:
            s = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(func.lower(User.fullname).like(s), func.lower(User.email).like(s))
            )

        # ========== 5) PAGINATION COUNT ==========
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar()

        # ========== 6) SORT ==========
        sort_map = {
            "progress": "progress",
            "price": "price_paid",
            "enrolled_at": CourseEnrollments.enrolled_at,
            "last_activity": "last_activity",
        }

        # sort after fetch → vì có trường computed
        order = order_dir.lower()

        # ========== 7) FETCH DATA ==========
        rows = (await self.db.execute(stmt)).all()

        students = []
        for (
            user_id,
            fullname,
            email,
            avatar,
            enrolled_at,
            last_accessed,
            completed_lessons,
            last_completed_at,
            price_paid,
        ) in rows:

            progress = (
                float(completed_lessons) / total_lessons * 100
                if total_lessons > 0
                else 0
            )

            last_activity = last_completed_at or last_accessed

            # ========= FILTER PROGRESS RANGE =========
            if min_progress is not None and progress < min_progress:
                continue
            if max_progress is not None and progress > max_progress:
                continue

            # ========= FILTER STATUS =========
            if status:
                if status == "not_started" and progress > 0:
                    continue
                if status == "learning" and not (0 < progress < 80):
                    continue
                if status == "almost" and not (80 <= progress < 100):
                    continue
                if status == "completed" and progress < 100:
                    continue

            students.append(
                {
                    "user_id": str(user_id),
                    "fullname": fullname,
                    "email": email,
                    "avatar": avatar,
                    "price_paid": float(price_paid or 0),
                    "progress_percent": round(progress, 2),
                    "completed_lessons": completed_lessons,
                    "total_lessons": total_lessons,
                    "enrolled_at": enrolled_at.isoformat() if enrolled_at else None,
                    "last_activity": (
                        last_activity.isoformat() if last_activity else None
                    ),
                }
            )

        # ========= SORTING =========
        if sort_by == "progress":
            students.sort(
                key=lambda x: x["progress_percent"], reverse=(order == "desc")
            )
        elif sort_by == "price":
            students.sort(key=lambda x: x["price_paid"], reverse=(order == "desc"))
        elif sort_by == "last_activity":
            students.sort(
                key=lambda x: x["last_activity"] or "", reverse=(order == "desc")
            )
        elif sort_by == "enrolled_at":
            students.sort(
                key=lambda x: x["enrolled_at"] or "", reverse=(order == "desc")
            )

        # ========= PAGINATION =========
        paged = students[(page - 1) * limit : page * limit]

        return {
            "course_id": str(course_id),
            "title": course.title,
            "page": page,
            "limit": limit,
            "total": total,
            "students": paged,
        }

    # ============================================================
    # 2) EXPORT CSV DANH SÁCH HỌC VIÊN
    # ============================================================
    async def export_course_students_csv_async(
        self,
        course_id: uuid.UUID,
        instructor_id: uuid.UUID,
        search: str | None = None,
        min_progress: float | None = None,
        max_progress: float | None = None,
        status: str | None = None,
        sort_by: str = "enrolled_at",
        order_dir: str = "desc",
    ) -> str:
        # Lấy toàn bộ (limit lớn)
        data = await self.get_course_students_list_async(
            course_id=course_id,
            instructor_id=instructor_id,
            page=1,
            limit=100000,  # đủ to
            search=search,
            min_progress=min_progress,
            max_progress=max_progress,
            status=status,
            sort_by=sort_by,
            order_dir=order_dir,
        )

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "user_id",
                "fullname",
                "email",
                "price_paid",
                "progress_percent",
                "completed_lessons",
                "total_lessons",
                "enrolled_at",
                "last_activity",
            ]
        )

        for s in data["students"]:
            writer.writerow(
                [
                    s["user_id"],
                    s["fullname"],
                    s["email"],
                    s["price_paid"],
                    s["progress_percent"],
                    s["completed_lessons"],
                    s["total_lessons"],
                    s["enrolled_at"],
                    s["last_activity"],
                ]
            )

        return output.getvalue()

    async def get_course_full_stats_async(
        self,
        course_id: uuid.UUID,
        instructor_id: uuid.UUID,
    ):
        # ======================================================
        # 1) LẤY COURSE + CURRICULUM (KHÔNG LAZY)
        # ======================================================
        course = await self.db.scalar(
            select(Courses)
            .where(Courses.id == course_id)
            .options(
                selectinload(Courses.course_sections).selectinload(
                    CourseSections.lessons
                )
            )
        )

        if not course:
            raise HTTPException(404, "Khóa học không tồn tại")

        if course.instructor_id != instructor_id:
            raise HTTPException(403, "Bạn không có quyền xem khóa học này")

        # Snapshot
        base_price = float(course.base_price or 0)
        views = int(course.views or 0)
        rating_avg = float(course.rating_avg or 0)
        total_reviews = int(course.total_reviews or 0)
        total_length_seconds = int(course.total_length_seconds or 0)

        # curriculum
        sections_count = len(course.course_sections)
        lessons_count = sum(len(s.lessons) for s in course.course_sections)

        # ======================================================
        # 2) THỐNG KÊ HỌC VIÊN (DỰA TRÊN ENROLLMENT + PURCHASE)
        # ======================================================

        # Tổng học viên
        total_students = (
            await self.db.scalar(
                select(func.count())
                .select_from(CourseEnrollments)
                .where(CourseEnrollments.course_id == course_id)
            )
            or 0
        )

        # Paid students (chỉ purchase_items có discounted_price > 0)
        paid_students = (
            await self.db.scalar(
                select(func.count(func.distinct(PurchaseItems.user_id)))
                .where(PurchaseItems.course_id == course_id)
                .where(PurchaseItems.status == "completed")
                .where(PurchaseItems.discounted_price > 0)
            )
            or 0
        )

        free_students = total_students - paid_students

        # ======================================================
        # 3) THỐNG KÊ TIẾN ĐỘ
        # ======================================================

        avg_progress = (
            await self.db.scalar(
                select(func.coalesce(func.avg(CourseEnrollments.progress), 0)).where(
                    CourseEnrollments.course_id == course_id
                )
            )
            or 0
        )

        completed_students = (
            await self.db.scalar(
                select(func.count())
                .where(CourseEnrollments.course_id == course_id)
                .where(CourseEnrollments.progress >= 100)
            )
            or 0
        )

        completion_rate = (
            round((completed_students / total_students) * 100, 2)
            if total_students > 0
            else 0
        )

        # ======================================================
        # 4) DOANH THU GIẢNG VIÊN (DỰA TRÊN instructor_earnings)
        # ======================================================

        # Lấy list transaction_id của khóa học này
        transaction_ids_subq = select(PurchaseItems.transaction_id).where(
            PurchaseItems.course_id == course_id
        )

        # Tổng tiền đã trả
        revenue_paid = (
            await self.db.scalar(
                select(func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0))
                .where(InstructorEarnings.transaction_id.in_(transaction_ids_subq))
                .where(InstructorEarnings.status == "paid")
            )
            or 0
        )

        # Tiền đang HOLD
        revenue_holding = (
            await self.db.scalar(
                select(func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0))
                .where(InstructorEarnings.transaction_id.in_(transaction_ids_subq))
                .where(InstructorEarnings.status == "holding")
            )
            or 0
        )

        # Tiền sắp trả
        revenue_pending = (
            await self.db.scalar(
                select(func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0))
                .where(InstructorEarnings.transaction_id.in_(transaction_ids_subq))
                .where(InstructorEarnings.status == "pending")
            )
            or 0
        )

        # ======================================================
        # 5) RETURN
        # ======================================================
        return {
            "course_id": str(course.id),
            "title": course.title,
            "thumbnail_url": course.thumbnail_url,
            "base_price": base_price,
            # Snapshot
            "views": views,
            "rating_avg": rating_avg,
            "total_reviews": total_reviews,
            # Curriculum
            "sections_count": sections_count,
            "lessons_count": lessons_count,
            "total_length_seconds": total_length_seconds,
            # Students
            "total_students": total_students,
            "paid_students": paid_students,
            "free_students": free_students,
            # Progress
            "avg_progress": float(avg_progress),
            "completed_students": completed_students,
            "completion_rate": completion_rate,
            # Revenue
            "revenue_paid": float(revenue_paid),
            "revenue_holding": float(revenue_holding),
            "revenue_pending": float(revenue_pending),
            # Approval
            "approval_status": course.approval_status,
            "review_round": course.review_round,
            "approved_at": (
                course.approved_at.isoformat() if course.approved_at else None
            ),
            "created_at": course.created_at.isoformat() if course.created_at else None,
            "updated_at": course.updated_at.isoformat() if course.updated_at else None,
        }

    async def get_course_activity_timeline_pro_async(
        self,
        course_id: uuid.UUID,
        instructor_id: uuid.UUID,
        mode: str = "day",  # day | month | quarter | year
    ):
        """
        Timeline PRODUCTION:
        - Thống kê lượt đăng ký & hoạt động học viên
        - Theo ngày / tháng / quý / năm
        """

        # ============================
        # 1) CHECK OWNERSHIP
        # ============================
        course = await self.db.scalar(select(Courses).where(Courses.id == course_id))
        if not course:
            raise HTTPException(404, "Khóa học không tồn tại.")

        if course.instructor_id != instructor_id:
            raise HTTPException(403, "Bạn không có quyền xem dữ liệu khóa học này.")

        # ============================
        # 2) LẤY DANH SÁCH HỌC VIÊN FULL
        # ============================
        data = await self.get_course_students_list_async(
            course_id=course_id,
            instructor_id=instructor_id,
            page=1,
            limit=200000,  # max
        )

        students = data["students"]

        enroll_map: dict[str, int] = {}
        activity_map: dict[str, int] = {}

        # ============================
        # 3) FORMAT KEY THEO MODE
        # ============================
        def make_key(dt_str: str | None):
            if not dt_str:
                return None

            dt = now_tzinfo().fromisoformat(dt_str)

            if mode == "day":
                return dt.strftime("%Y-%m-%d")

            if mode == "month":
                return dt.strftime("%Y-%m")  # 2025-02

            if mode == "quarter":
                q = (dt.month - 1) // 3 + 1
                return f"{dt.year}-Q{q}"

            if mode == "year":
                return str(dt.year)

            return dt.strftime("%Y-%m-%d")

        # ============================
        # 4) GOM DỮ LIỆU
        # ============================
        for s in students:
            # ========== ENROLL ==========
            if s["enrolled_at"]:
                k = make_key(s["enrolled_at"])
                if k:
                    enroll_map[k] = enroll_map.get(k, 0) + 1

            # ========== ACTIVITY ==========
            if s["last_activity"]:
                k2 = make_key(s["last_activity"])
                if k2:
                    activity_map[k2] = activity_map.get(k2, 0) + 1

        # ============================
        # 5) SORT + FORMAT OUTPUT
        # ============================

        enroll_series = [{"time": k, "count": v} for k, v in sorted(enroll_map.items())]

        activity_series = [
            {"time": k, "count": v} for k, v in sorted(activity_map.items())
        ]

        return {
            "course_id": data["course_id"],
            "title": data["title"],
            "mode": mode,
            "enroll_timeline": enroll_series,
            "activity_timeline": activity_series,
        }

    async def get_all_categories_sorted_by_name(self):
        """
        Lấy toàn bộ danh mục, sắp xếp theo tên (A-Z), dùng cho giảng viên khi tạo khóa học.
        """
        try:
            stmt = (
                select(
                    Categories.id,
                    Categories.name,
                    Categories.slug,
                    Categories.parent_id,
                    Categories.order_index,
                )
                .order_by(asc(Categories.name))
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            return [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "slug": row.slug,
                    "parent_id": str(row.parent_id) if row.parent_id else None,
                    "order_index": row.order_index or 0,
                }
                for row in rows
            ]

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lấy danh sách danh mục: {e}",
            )