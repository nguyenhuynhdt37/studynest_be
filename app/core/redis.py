from __future__ import annotations

from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.settings import settings


_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


async def ping_redis() -> bool:
    try:
        await get_redis().ping()
        return True
    except Exception as exc:
        logger.warning(f"[Redis] unavailable: {exc}")
        return False


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
