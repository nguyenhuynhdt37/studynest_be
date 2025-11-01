import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

# ===== IMPORT ROUTERS =====
from app.api.v1 import auth

# --- ADMIN ROUTES ---
from app.api.v1.admin import category as admin_category
from app.api.v1.admin import lecturer as admin_lecturer
from app.api.v1.admin import role
from app.api.v1.admin import topic as admin_topic
from app.api.v1.admin import user as admin_user

# --- CHAT / AI ROUTES ---
from app.api.v1.chat.admin import topic as chat_topic_admin
from app.api.v1.chat.lecturer import course as chat_course_lecturer

# --- LECTURER ROUTES ---
from app.api.v1.lecturer import chapter, lesson
from app.api.v1.lecturer import courses as lecturer_courses

# --- USER ROUTES ---
from app.api.v1.user import category, favorites, learning, learning_fields
from app.api.v1.user import courses as user_courses

# --- MIDDLEWARE ---
from app.middleware.request_context import RequestContextMiddleware

# ===== APP CONFIG =====
app = FastAPI(
    title="FastAPI Starter 2025",
    description="Backend demo với cấu hình trong main.py",
    version="0.1.0",
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

# --- AUTH ---
app.include_router(auth.router, prefix=prefix)

# --- USER ROUTES ---
app.include_router(category.router, prefix=prefix)
app.include_router(user_courses.router, prefix=prefix)
app.include_router(favorites.router, prefix=prefix)
app.include_router(learning.router, prefix=prefix)
app.include_router(learning_fields.router, prefix=prefix)

# --- LECTURER ROUTES ---
app.include_router(lecturer_courses.router, prefix=prefix)
app.include_router(lesson.router, prefix=prefix)
app.include_router(chapter.router, prefix=prefix)

# --- ADMIN ROUTES ---
app.include_router(admin_user.router, prefix=prefix)
app.include_router(admin_lecturer.router, prefix=prefix)
app.include_router(admin_category.router, prefix=prefix)
app.include_router(admin_topic.router, prefix=prefix)
app.include_router(role.router, prefix=prefix)

# --- CHAT / AI ROUTES ---
app.include_router(chat_topic_admin.router, prefix=prefix)
app.include_router(chat_course_lecturer.router, prefix=prefix)


# ===== ROOT =====
@app.get("/")
async def hello_world():
    return {"message": "Hello world"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
