import uuid
from typing import Optional

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding import EmbeddingService, get_embedding_service
from app.core.ws_manager import ws_manager
from app.db.models.database import Notifications
from app.db.sesson import get_session
from app.libs.formats.datetime import now as get_now
from app.libs.formats.datetime import serialize, to_utc_naive
from app.schemas.shares.notification import NotificationCreateSchema


class NotificationService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        embedding: EmbeddingService = Depends(get_embedding_service),
    ):
        self.db = db

    # ==========================================================================
    # 📋 Lấy danh sách thông báo (đã thêm try/catch)
    # ==========================================================================
    async def get_notifications_async(
        self,
        user_id: uuid.UUID | None,
        role: str,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        type_: Optional[str] = None,
        is_read: Optional[bool] = None,
        sort_by: str = "created_at",
        order_dir: str = "desc",
    ):
        try:
            valid_sort_fields = {
                "title": Notifications.title,
                "type": Notifications.type,
                "is_read": Notifications.is_read,
                "created_at": Notifications.created_at,
                "read_at": Notifications.read_at,
            }

            sort_field = valid_sort_fields.get(sort_by, Notifications.created_at)
            sort_order = (
                sort_field.desc() if order_dir.lower() == "desc" else sort_field.asc()
            )

            # ADMIN → KHÔNG lọc user_id
            if role == "ADMIN":
                base_stmt = select(Notifications).where(
                    Notifications.role_target.op("&&")(["ADMIN"])
                )
            else:
                if not user_id:
                    raise HTTPException(400, "Thiếu user_id.")

                base_stmt = (
                    select(Notifications)
                    .where(Notifications.user_id == user_id)
                    .where(Notifications.role_target.op("&&")([role, "all"]))
                )

            # Type filter
            if type_:
                base_stmt = base_stmt.where(Notifications.type == type_)

            # Read filter
            if is_read is not None:
                base_stmt = base_stmt.where(Notifications.is_read.is_(is_read))

            # Search
            if search:
                keyword = f"%{search.lower()}%"
                base_stmt = base_stmt.where(
                    Notifications.title.ilike(keyword)
                    | Notifications.content.ilike(keyword)
                )

            # Total
            total_stmt = select(func.count()).select_from(base_stmt.subquery())
            total = (await self.db.execute(total_stmt)).scalar_one()

            # Unread
            if role == "ADMIN":
                unread_stmt = (
                    select(func.count())
                    .select_from(Notifications)
                    .where(Notifications.role_target.op("&&")(["ADMIN"]))
                    .where(Notifications.is_read.is_(False))
                )
            else:
                unread_stmt = (
                    select(func.count())
                    .select_from(Notifications)
                    .where(Notifications.user_id == user_id)
                    .where(Notifications.role_target.op("&&")([role, "all"]))
                    .where(Notifications.is_read.is_(False))
                )

            unread = (await self.db.execute(unread_stmt)).scalar_one()

            # Pagination
            offset = (page - 1) * limit
            items_stmt = base_stmt.order_by(sort_order).limit(limit).offset(offset)
            items = (await self.db.execute(items_stmt)).scalars().all()

            return {
                "total": total,
                "page": page,
                "limit": limit,
                "unread": unread,
                "items": items,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"[Notifications][Get] Lỗi truy vấn: {e}")
            raise HTTPException(500, "Lỗi hệ thống khi lấy thông báo.")

    # ==========================================================================
    # 📨 Tạo thông báo + WS (đã thêm try/catch)
    # ==========================================================================
    async def create_notification_async(
        self,
        schema: NotificationCreateSchema,
    ) -> Notifications:
        try:
            # ----------------------------------
            # Chuẩn hóa role_target
            # ----------------------------------
            if not schema.role_target:
                roles = ["USER"]
            else:
                roles = (
                    [schema.role_target]
                    if isinstance(schema.role_target, str)
                    else schema.role_target
                )

            notif = Notifications(
                id=uuid.uuid4(),
                user_id=schema.user_id or None,
                title=schema.title,
                content=schema.content,
                url=schema.url,
                type=schema.type or "system",
                role_target=roles,
                metadata_=schema.metadata or {},
                action=schema.action or "open_url",
                is_read=False,
                created_at=await to_utc_naive(get_now()),
            )

            self.db.add(notif)
            await self.db.commit()
            await self.db.refresh(notif)

        except Exception as e:
            logger.exception(f"[Notifications][Create] Lỗi tạo thông báo: {e}")
            await self.db.rollback()
            raise HTTPException(500, "Lỗi hệ thống khi tạo thông báo.")

        # ==========================================================================
        # 🛰 Gửi WebSocket (KHÔNG ảnh hưởng DB nếu lỗi)
        # ==========================================================================
        try:
            payload = {
                "type": "notification.created",
                "data": {
                    "id": str(notif.id),
                    "user_id": str(notif.user_id),
                    "title": notif.title,
                    "content": notif.content,
                    "url": notif.url,
                    "type": notif.type,
                    "role_target": notif.role_target or [],
                    "metadata": notif.metadata_ or {},
                    "action": notif.action,
                    "is_read": notif.is_read,
                    "read_at": (
                        await to_utc_naive(notif.read_at) if notif.read_at else None
                    ),
                    "created_at": await to_utc_naive(notif.created_at),
                    "updated_at": await to_utc_naive(notif.updated_at),
                },
            }

            payload = await serialize(payload)

            # Broadcast theo từng role
            user_id = str(notif.user_id) if notif.user_id else None

            for r in roles:
                if r == "ADMIN":
                    channel = "ADMIN"  # admin lấy chung
                else:
                    channel = f"{r}_{user_id}"

                logger.info(f"[WS][Notifications] Broadcasting to {channel}")
                await ws_manager.broadcast(channel, payload)

        except Exception as ws_err:
            # KHÔNG rollback DB — chỉ log
            logger.exception(f"[Notifications][WS] Lỗi WebSocket: {ws_err}")

        return notif

    async def mark_all_as_read(self, user_id: str, role: str):
        try:
            stmt = (
                update(Notifications)
                .where(
                    Notifications.user_id == user_id,
                    Notifications.is_read.is_(False),
                    or_(
                        func.cardinality(Notifications.role_target)
                        == 0,  # thông báo chung
                        Notifications.role_target.op("@>")([role]),  # chứa role
                    ),
                )
                .values(
                    is_read=True,
                    read_at=get_now(),
                )
            )

            await self.db.execute(stmt)
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise e

    async def mark_as_read(self, notification_id: uuid.UUID, user_id: uuid.UUID):
        try:
            stmt = (
                update(Notifications)
                .where(
                    Notifications.id == notification_id,
                    Notifications.user_id == user_id,
                    Notifications.is_read.is_(False),  # chỉ update khi chưa đọc
                )
                .values(
                    is_read=True,
                    read_at=get_now(),
                )
                .returning(Notifications.id)
            )

            result = await self.db.execute(stmt)
            updated_id = result.scalar_one_or_none()

            # Không tìm thấy hoặc không phải owner -> coi như không làm gì
            if not updated_id:
                raise HTTPException(404, "Thông báo không tồn tại hoặc đã được đọc.")

            await self.db.commit()
            return {
                "success": True,
                "message": "Đã đánh dấu đã đọc.",
                "id": str(updated_id),
            }

        except Exception as e:
            await self.db.rollback()
            raise e
