from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger

from app.core.redis import get_redis
from app.core.settings import settings
from app.schemas.shares.presence import PresenceResponse


class PresenceService:
    def __init__(self) -> None:
        self.ttl_seconds = max(settings.PRESENCE_TTL_SECONDS, 30)

    def _presence_key(self, user_id: str) -> str:
        return f"presence:user:{user_id}"

    def _connections_key(self, user_id: str) -> str:
        return f"presence:user:{user_id}:connections"

    async def mark_online(self, user_id: str, connection_id: str) -> None:
        await self._touch(user_id=user_id, connection_id=connection_id, status="online")

    async def heartbeat(self, user_id: str, connection_id: str, status: str = "online") -> None:
        await self._touch(user_id=user_id, connection_id=connection_id, status=status)

    async def mark_offline(self, user_id: str, connection_id: str) -> None:
        try:
            redis = get_redis()
            connections_key = self._connections_key(user_id)
            await redis.srem(connections_key, connection_id)
            connection_count = await redis.scard(connections_key)

            if connection_count > 0:
                await redis.expire(connections_key, self.ttl_seconds)
                await self._write_presence(user_id, "online", int(connection_count), self.ttl_seconds)
                return

            await redis.delete(connections_key)
            await self._write_presence(user_id, "offline", 0, self.ttl_seconds * 24)
        except Exception as exc:
            logger.warning(f"[Presence] mark_offline skipped for {user_id}: {exc}")

    async def get_presence(self, user_id: str) -> PresenceResponse:
        try:
            redis = get_redis()
            data = await redis.hgetall(self._presence_key(user_id))
            if not data:
                return PresenceResponse(user_id=user_id, status="offline")

            return self._to_response(user_id, data)
        except Exception as exc:
            logger.warning(f"[Presence] get_presence failed for {user_id}: {exc}")
            return PresenceResponse(user_id=user_id, status="offline")

    async def get_bulk_presence(self, user_ids: Iterable[str]) -> dict[str, PresenceResponse]:
        normalized_ids = list(dict.fromkeys(str(user_id) for user_id in user_ids if user_id))
        if not normalized_ids:
            return {}

        try:
            redis = get_redis()
            pipe = redis.pipeline()
            for user_id in normalized_ids:
                pipe.hgetall(self._presence_key(user_id))
            rows = await pipe.execute()

            return {
                user_id: self._to_response(user_id, data) if data else PresenceResponse(user_id=user_id, status="offline")
                for user_id, data in zip(normalized_ids, rows)
            }
        except Exception as exc:
            logger.warning(f"[Presence] get_bulk_presence failed: {exc}")
            return {
                user_id: PresenceResponse(user_id=user_id, status="offline")
                for user_id in normalized_ids
            }

    async def _touch(self, user_id: str, connection_id: str, status: str) -> None:
        try:
            redis = get_redis()
            connections_key = self._connections_key(user_id)
            await redis.sadd(connections_key, connection_id)
            await redis.expire(connections_key, self.ttl_seconds)
            connection_count = await redis.scard(connections_key)
            await self._write_presence(user_id, status, int(connection_count), self.ttl_seconds)
        except Exception as exc:
            logger.warning(f"[Presence] touch skipped for {user_id}: {exc}")

    async def _write_presence(
        self,
        user_id: str,
        status: str,
        connection_count: int,
        ttl_seconds: int,
    ) -> None:
        redis = get_redis()
        key = self._presence_key(user_id)
        await redis.hset(
            key,
            mapping={
                "status": status,
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "connection_count": str(connection_count),
            },
        )
        await redis.expire(key, ttl_seconds)

    def _to_response(self, user_id: str, data: dict[str, str]) -> PresenceResponse:
        last_seen_raw = data.get("last_seen_at")
        last_seen_at = None
        if last_seen_raw:
            try:
                last_seen_at = datetime.fromisoformat(last_seen_raw)
            except ValueError:
                last_seen_at = None

        try:
            connection_count = int(data.get("connection_count") or 0)
        except ValueError:
            connection_count = 0

        status = data.get("status") or "offline"
        if status not in {"online", "offline", "away"}:
            status = "offline"

        return PresenceResponse(
            user_id=user_id,
            status=status,
            last_seen_at=last_seen_at,
            connection_count=connection_count,
        )
