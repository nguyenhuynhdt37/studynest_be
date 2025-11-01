# app/services/lecturer/course_service.py
import math
import uuid
from datetime import datetime
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, HTTPException, UploadFile
from slugify import slugify
from sqlalchemy import asc, case, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import EmbeddingService
from app.db.models.database import (
    Categories,
    Courses,
    CourseSections,
    Topics,
    Transactions,
    User,
)
from app.db.sesson import AsyncSessionLocal, get_session
from app.libs.formats.datetime import to_utc_naive
from app.schemas.lecturer.courses import CreateCourse, UpdateCourse
from app.services.shares.google_driver import GoogleDriveService


class CourseService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive: GoogleDriveService = Depends(GoogleDriveService),
        embedding: EmbeddingService = Depends(EmbeddingService),
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
                created_at=to_utc_naive(datetime.utcnow()),
                updated_at=to_utc_naive(datetime.utcnow()),
            )

            # 6️⃣ Lưu DB ngay để có course_id
            self.db.add(new_course)
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

                embed_service = EmbeddingService()
                vector = await embed_service.embed_google_3072(text_for_embed)

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
                course.embedding_updated_at = to_utc_naive(datetime.utcnow())
                course.updated_at = to_utc_naive(datetime.utcnow())

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
        update_data["updated_at"] = to_utc_naive(datetime.utcnow())

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

                embed_service = EmbeddingService()
                vector = await embed_service.embed_google_3072(text_for_embed)

                await db.execute(
                    update(Courses)
                    .where(Courses.id == course_id)
                    .values(
                        embedding=vector,
                        embedding_updated_at=to_utc_naive(datetime.utcnow()),
                        updated_at=to_utc_naive(datetime.utcnow()),
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

        # 3️⃣ Cho phép xóa
        await self.db.execute(delete(Courses).where(Courses.id == course_id))
        await self.db.commit()

        return {"message": "✅ Đã xóa khóa học thành công"}
