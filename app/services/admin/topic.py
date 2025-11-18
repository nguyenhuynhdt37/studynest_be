from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, Depends, HTTPException
from slugify import slugify
from sqlalchemy import asc, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService, get_embedding_service
from app.db.models.database import Categories, Courses, Topics
from app.db.sesson import AsyncSessionLocal, get_session
from app.libs.formats.datetime import now as get_now, to_utc_naive
from app.schemas.admin.topic import TopicCreate, TopicUpdate


class TopicService:
    def __init__(self, db: AsyncSession = Depends(get_session)) -> None:
        self.db = db

    async def create_topic_async(
        self, schema: TopicCreate, background_tasks: BackgroundTasks
    ):
        category_exists = await self.db.scalar(
            select(Categories.id).where(Categories.id == schema.category_id)
        )
        if not category_exists:
            raise HTTPException(status_code=404, detail="❌ Category khsông tồn tại")
        slug = slugify(schema.name or schema.name, allow_unicode=True)
        slug_exists = await self.db.scalar(select(Topics.id).where(Topics.slug == slug))
        if slug_exists:
            raise HTTPException(
                status_code=400, detail="⚠️ Slug đã tồn tại, vui lòng chọn slug khác"
            )

        max_index = await self.db.scalar(
            select(func.coalesce(func.max(Topics.order_index), 0)).where(
                Topics.category_id == schema.category_id
            )
        )
        new_order = (max_index or 0) + 1

        new_topic = Topics(
            **schema.dict(),
            order_index=new_order,
            slug=slug,
            created_at=await to_utc_naive(get_now()),
            updated_at=await to_utc_naive(get_now()),
        )

        self.db.add(new_topic)
        await self.db.commit()
        await self.db.refresh(new_topic)
        text = f"Tên topic: {new_topic.name}, Mô tả: {new_topic.description}"
        background_tasks.add_task(
            TopicService.process_embedding_create_async, new_topic.id, text
        )
        return new_topic

    @staticmethod
    async def process_embedding_create_async(topic_id: UUID, text: str):
        async with AsyncSessionLocal() as db:
            try:
                embedding = await get_embedding_service()
                vector = await embedding.embed_google_normalized(text)
                await db.execute(
                    update(Topics)
                    .where(Topics.id == topic_id)
                    .values(
                        embedding=vector,
                        updated_at=await to_utc_naive(get_now()),
                    )
                )
                await db.commit()
                print(f"✅ [{topic_id}] Embedding thành công.")
            except Exception as e:
                await db.rollback()
                print(f"❌ Lỗi khi xử lý embedding cho {topic_id}: {e}")

    async def get_topics_async(
        self,
        page: int,
        limit: int,
        category_id: Optional[UUID],
        is_active: Optional[bool],
        search: Optional[str],
        sort_by: Optional[str],
        sort_order: Optional[str],
    ):
        try:
            # ===== Query gốc: join + group by =====
            query = (
                select(
                    Topics.id,
                    Topics.name,
                    Topics.slug,
                    Topics.description,
                    Topics.category_id,
                    Categories.name.label("category_name"),
                    Topics.order_index,
                    Topics.is_active,
                    Topics.created_at,
                    Topics.updated_at,
                    func.count(Courses.id).label("total_courses"),
                )
                .join(Categories, Topics.category_id == Categories.id)
                .outerjoin(Courses, Courses.topic_id == Topics.id)
                .group_by(Topics.id, Categories.name)
            )

            # ===== Lọc =====
            if category_id:
                query = query.where(Topics.category_id == category_id)
            if is_active is not None:
                query = query.where(Topics.is_active == is_active)
            if search:
                query = query.where(
                    or_(
                        Topics.name.ilike(f"%{search}%"),
                        Topics.slug.ilike(f"%{search}%"),
                        Topics.description.ilike(f"%{search}%"),
                    )
                )

            # ===== Sắp xếp =====
            if sort_by == "total_courses":
                order_field = func.count(Courses.id)
            else:
                order_field = getattr(Topics, sort_by, Topics.order_index)

            query = query.order_by(
                desc(order_field) if sort_order == "desc" else asc(order_field)
            )

            # ===== Phân trang =====
            offset = (page - 1) * limit
            query = query.offset(offset).limit(limit)
            result = await self.db.execute(query)
            topics = result.all()

            # ===== Tổng số bản ghi =====
            total = await self.db.scalar(select(func.count()).select_from(Topics))

            return {
                "meta": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit,
                },
                "data": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "description": t.description,
                        "category_id": t.category_id,
                        "category_name": t.category_name,
                        "order_index": t.order_index,
                        "is_active": t.is_active,
                        "total_courses": t.total_courses,
                        "created_at": t.created_at,
                        "updated_at": t.updated_at,
                    }
                    for t in topics
                ],
            }

        except Exception as e:
            raise HTTPException(500, f"Lỗi khi lấy danh sách topic: {e}")

    async def delete_topic_async(self, topic_id: UUID):
        """Xóa topic mà không làm ảnh hưởng tới các khóa học."""
        # 1️⃣ Kiểm tra topic tồn tại
        topic = await self.db.scalar(select(Topics).where(Topics.id == topic_id))
        if not topic:
            raise HTTPException(404, "❌ Không tìm thấy topic để xóa")

        try:
            await self.db.execute(
                update(Courses)
                .where(Courses.topic_id == topic_id)
                .values(topic_id=None)
            )

            # 3️⃣ Xóa topic
            await self.db.execute(delete(Topics).where(Topics.id == topic_id))
            await self.db.commit()

            return {
                "message": f"✅ Đã xóa topic '{topic.name}' và giữ nguyên các khóa học liên quan."
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"❌ Lỗi khi xóa topic: {e}")

    async def update_topic_async(
        self,
        topic_id: UUID,
        schema: TopicUpdate,
        background_tasks: BackgroundTasks,
    ):
        """Cập nhật topic, nếu đổi tên hoặc mô tả → làm lại embedding."""
        # 1️⃣ Kiểm tra topic tồn tại
        topic = await self.db.scalar(select(Topics).where(Topics.id == topic_id))
        if not topic:
            raise HTTPException(404, "❌ Không tìm thấy topic để cập nhật")

        # 2️⃣ Kiểm tra có thay đổi tên hoặc mô tả không
        should_re_embed = False
        if schema.name and schema.name.strip() != topic.name.strip():
            topic.name = schema.name.strip()
            should_re_embed = True

        if (
            schema.description
            and schema.description.strip() != (topic.description or "").strip()
        ):
            topic.description = schema.description.strip()
            should_re_embed = True

        # 3️⃣ Cập nhật các trường khác nếu có
        if schema.is_active is not None:
            topic.is_active = schema.is_active

        topic.updated_at = await to_utc_naive(get_now())

        # 4️⃣ Lưu thay đổi
        await self.db.commit()
        await self.db.refresh(topic)

        # 5️⃣ Nếu thay đổi tên/description → làm lại embedding
        if should_re_embed:
            text = f"Tên topic: {topic.name}. Mô tả: {topic.description or 'Chưa có mô tả'}."
            background_tasks.add_task(
                TopicService.process_embedding_update_async, topic.id, text
            )

        return {
            "message": "✅ Cập nhật topic thành công",
            "re_embedded": should_re_embed,
            "data": {
                "id": str(topic.id),
                "name": topic.name,
                "description": topic.description,
                "slug": topic.slug,
                "category_id": str(topic.category_id),
                "is_active": topic.is_active,
                "updated_at": topic.updated_at,
            },
        }

    @staticmethod
    async def process_embedding_update_async(topic_id: UUID, text: str):
        """Xử lý tái tạo embedding nền."""
        async with AsyncSessionLocal() as db:
            try:
                embedding = await get_embedding_service()
                vector = await embedding.embed_google_normalized(text)

                await db.execute(
                    update(Topics)
                    .where(Topics.id == topic_id)
                    .values(
                        embedding=vector,
                        updated_at=await to_utc_naive(get_now()),
                    )
                )
                await db.commit()
                print(f"✅ [Re-embed] Cập nhật embedding cho topic {topic_id}")

            except Exception as e:
                await db.rollback()
                print(f"❌ Lỗi khi re-embed topic {topic_id}: {e}")

    async def get_topic_by_id_async(self, topic_id: UUID):
        """Lấy thông tin chi tiết 1 topic, kèm thống kê số khóa học."""
        # 1️⃣ Lấy topic
        topic = await self.db.scalar(select(Topics).where(Topics.id == topic_id))
        if not topic:
            raise HTTPException(404, "❌ Không tìm thấy topic")

        # 2️⃣ Đếm số khóa học thuộc topic
        course_count = await self.db.scalar(
            select(func.count())
            .select_from(Courses)
            .where(Courses.topic_id == topic_id)
        )

        # 3️⃣ Trả về dữ liệu
        return {
            "id": str(topic.id),
            "category_id": str(topic.category_id),
            "name": topic.name,
            "slug": topic.slug,
            "description": topic.description,
            "order_index": topic.order_index,
            "is_active": topic.is_active,
            "has_embedding": topic.embedding is not None,
            "course_count": course_count or 0,
            "created_at": topic.created_at,
            "updated_at": topic.updated_at,
        }
