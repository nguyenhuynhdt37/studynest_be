from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

# --- ADMIN ROUTES ---
from app.api.v1.admin import category as admin_category
from app.api.v1.admin import discounts as admin_discounts
from app.api.v1.admin import lecturer as admin_lecturer
from app.api.v1.admin import platform_wallet_service, role
from app.api.v1.admin import refunds as admin_refunds
from app.api.v1.admin import topic as admin_topic
from app.api.v1.admin import transactions as admin_transactions
from app.api.v1.admin import user as admin_user

# --- CHAT / AI ROUTES ---
from app.api.v1.chat.admin import topic as chat_topic_admin
from app.api.v1.chat.lecturer import course as chat_course_lecturer
from app.api.v1.chat.lecturer import lesson as chat_lesson_lecturer
from app.api.v1.chat.user import profile as chat_profile_user

# --- LECTURER ROUTES ---
from app.api.v1.lecturer import chapter, lesson
from app.api.v1.lecturer import courses as lecturer_courses
from app.api.v1.lecturer import discounts as lecturer_discounts
from app.api.v1.lecturer import refunds as lecturer_refunds
from app.api.v1.lecturer import transactions as lecturer_transactions
from app.api.v1.lecturer import wallet as lecturer_wallets

# ===== IMPORT ROUTERS =====
from app.api.v1.shares import auth, location, notification, upload, wallets

# --- USER ROUTES ---
from app.api.v1.user import category, favorites, learning, learning_fields
from app.api.v1.user import course_enroll as course_enroll
from app.api.v1.user import courses as user_courses
from app.api.v1.user import discounts as user_discounts
from app.api.v1.user import profile as user_profile
from app.api.v1.user import refunds as user_refunds
from app.api.v1.user import transaction as user_transaction
from app.core.scheduler import scheduler, start_scheduler

# --- MIDDLEWARE ---
from app.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):

    # ================================
    # 1) GLOBAL HTTP CLIENT
    # ================================
    app.state.http = httpx.AsyncClient(timeout=30)
    print("🌐 HTTP client started")

    # ================================
    # 2) START APSCHEDULER
    # ================================
    start_scheduler()
    print("⏱ Scheduler started")

    # App chạy
    try:
        yield
    finally:
        # ================================
        # 3) CLOSE HTTP CLIENT
        # ================================
        await app.state.http.aclose()
        print("🌐 HTTP client closed")

        # ================================
        # 4) STOP SCHEDULER
        # ================================
        try:
            scheduler.shutdown(wait=False)
            print("🛑 Scheduler stopped")
        except Exception as e:
            print("⚠ Scheduler shutdown error:", e)


# ===== APP CONFIG =====
app = FastAPI(
    title="FastAPI Starter 2025",
    description="Backend demo với cấu hình trong main.py",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


app.add_middleware(RequestContextMiddleware)
add_pagination(app)
prefix = "/api/v1"

# ===== REGISTER ROUTERS =====

# --- Share ---
app.include_router(auth.router, prefix=prefix)
app.include_router(location.router, prefix=prefix)
app.include_router(wallets.router, prefix=prefix)
app.include_router(notification.router, prefix=prefix)
app.include_router(upload.router, prefix=prefix)

# --- USER ROUTES ---
app.include_router(category.router, prefix=prefix)
app.include_router(user_courses.router, prefix=prefix)
app.include_router(course_enroll.router, prefix=prefix)
app.include_router(favorites.router, prefix=prefix)
app.include_router(learning.router, prefix=prefix)
app.include_router(learning_fields.router, prefix=prefix)
app.include_router(user_profile.router, prefix=prefix)
app.include_router(user_transaction.router, prefix=prefix)
app.include_router(user_discounts.router, prefix=prefix)
app.include_router(user_refunds.router, prefix=prefix)

# --- LECTURER ROUTES ---
app.include_router(lecturer_courses.router, prefix=prefix)
app.include_router(lesson.router, prefix=prefix)
app.include_router(chapter.router, prefix=prefix)
app.include_router(lecturer_discounts.router, prefix=prefix)
app.include_router(lecturer_wallets.router, prefix=prefix)
app.include_router(lecturer_transactions.router, prefix=prefix)
app.include_router(lecturer_refunds.router, prefix=prefix)

# --- ADMIN ROUTES ---
app.include_router(admin_user.router, prefix=prefix)
app.include_router(admin_lecturer.router, prefix=prefix)
app.include_router(admin_category.router, prefix=prefix)
app.include_router(admin_topic.router, prefix=prefix)
app.include_router(role.router, prefix=prefix)
app.include_router(platform_wallet_service.router, prefix=prefix)
app.include_router(admin_discounts.router, prefix=prefix)
app.include_router(admin_transactions.router, prefix=prefix)
app.include_router(admin_refunds.router, prefix=prefix)

# --- CHAT / AI ROUTES ---
app.include_router(chat_topic_admin.router, prefix=prefix)
app.include_router(chat_course_lecturer.router, prefix=prefix)
app.include_router(chat_lesson_lecturer.router, prefix=prefix)
app.include_router(chat_profile_user.router, prefix=prefix)


# ===== ROOT =====
@app.get("/")
async def hello_world():
    return {"message": "Hello world"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
