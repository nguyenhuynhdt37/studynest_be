# app/database.py
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_ASYNC_URL",
    "postgresql+asyncpg://huynh:Huynh2004@localhost:5432/elearn",
)

# ✅ Tạo engine async
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # bật True chỉ khi debug
    pool_pre_ping=True,  # tự kiểm tra connection còn sống
)

# ✅ Tạo session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 👈 Quan trọng nhất: giữ context sau commit, không greenlet lỗi
)

# ✅ Dependency cho FastAPI


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
