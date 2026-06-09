# StudyNest Backend — CLAUDE.md

> **Mục đích**: File này giúp Claude AI (hoặc bất kỳ AI assistant nào) hiểu đầy đủ codebase,
> áp dụng đúng pattern, và viết code nhất quán với dự án này.

---

## 🗂️ Tech Stack

| Layer          | Công nghệ                                     | Phiên bản |
| -------------- | --------------------------------------------- | --------- |
| Framework      | FastAPI                                       | >= 0.115  |
| Runtime server | Uvicorn                                       | >= 0.37   |
| ORM            | SQLAlchemy (async)                            | >= 2.0    |
| Database       | PostgreSQL                                    | 16+       |
| Vector DB      | pgvector                                      | >= 0.3    |
| Migration      | Alembic                                       | >= 1.13   |
| Schema/DTO     | Pydantic v2                                   | >= 2.8    |
| Auth           | PyJWT + bcrypt                                | -         |
| AI / LLM       | Google Gemini API + LangChain                 | -         |
| Embedding      | google-generativeai + pgvector (VECTOR 1536d) | -         |
| Email          | fastapi-mail                                  | -         |
| File Storage   | Google Drive API                              | -         |
| Code Execution | Piston API (Docker sandbox)                   | -         |
| Payment        | PayPal REST API                               | -         |
| Task Scheduler | APScheduler                                   | -         |
| Pagination     | fastapi-pagination + sqlakeyset               | -         |
| WebSocket      | FastAPI native WebSocket                      | -         |
| Config         | pydantic-settings (`.env`)                    | -         |

---

## 📁 Cấu Trúc Thư Mục

```
studynest_be/
├── app/
│   ├── main.py                     # Entry point: khởi tạo FastAPI, CORS,
│   │                               # đăng ký tất cả routers, lifespan
│   │
│   ├── api/v1/                     # 🎮 Controllers (chỉ xử lý HTTP layer)
│   │   ├── admin/                  # Endpoints dành cho ADMIN
│   │   ├── lecturer/               # Endpoints dành cho LECTURER
│   │   ├── user/                   # Endpoints dành cho USER (học viên)
│   │   ├── shares/                 # Endpoints dùng chung (auth, upload,
│   │   │                           #   profile, notification, location)
│   │   └── chat/                   # Endpoints AI Chat
│   │       ├── admin/              # Chat context admin
│   │       ├── lecturer/           # Chat context giảng viên
│   │       └── user/               # Chat context học viên
│   │
│   ├── services/                   # 🧠 Business Logic Layer
│   │   ├── admin/
│   │   ├── lecturer/
│   │   ├── user/
│   │   ├── shares/
│   │   └── chat/
│   │
│   ├── schemas/                    # 📋 DTOs (Pydantic v2 models)
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── lecturer/
│   │   ├── user/
│   │   ├── shares/
│   │   └── chat/
│   │
│   ├── db/
│   │   ├── models/database.py      # ⚠️ TẤT CẢ SQLAlchemy entity ở đây
│   │   ├── base.py                 # DeclarativeBase
│   │   └── sesson.py               # engine, AsyncSessionLocal, get_session()
│   │
│   ├── core/
│   │   ├── settings.py             # Settings từ .env (pydantic-settings)
│   │   ├── deps.py                 # AuthorizationService (DI + RBAC)
│   │   ├── security.py             # SecurityService: JWT, bcrypt, OTP
│   │   ├── embedding.py            # Vector embedding logic (Gemini + pgvector)
│   │   ├── llm.py                  # LLM wrapper (Gemini Generative AI)
│   │   ├── scheduler.py            # APScheduler job definitions
│   │   ├── context.py              # get_request() – async request context
│   │   ├── enum.py                 # Các Enum dùng chung toàn project
│   │   └── ws_manager.py           # WebSocket connection manager
│   │
│   ├── middleware/
│   │   └── request_context.py      # Inject request vào contextvar global
│   │
│   ├── libs/
│   │   └── formats/
│   │       └── datetime.py         # now(), now_tzinfo(), to_utc_naive()
│   │
│   └── templates/                  # Jinja2 templates (email, v.v.)
│
├── docs/                           # API documentation markdown
├── .env                            # Environment variables (KHÔNG commit)
├── requirements.txt
├── docker-compose.yaml             # Piston API (code execution sandbox)
├── CLAUDE.md                       # ← file này
└── PROJECT_STRUCTURE.md
```

---

## 🔄 Pattern Chuẩn: Tạo Feature Mới (4 bước)

### Bước 1 — Schema (DTO)

**File**: `app/schemas/<domain>/<feature>.py`

```python
from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class CreateCourseRequest(BaseModel):
    title: str
    description: Optional[str] = None

class CourseResponse(BaseModel):
    id: UUID
    title: str
    is_published: bool

    model_config = {"from_attributes": True}
```

> **Rule**: Luôn có `model_config = {"from_attributes": True}` cho response schema
> để `.model_validate(orm_object)` hoạt động đúng.

---

### Bước 2 — Service (Business Logic)

**File**: `app/services/<domain>/<feature>.py`

```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import Courses
from app.db.sesson import get_session

class CourseService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def get_courses_async(self) -> list[Courses]:
        result = await self.db.execute(
            select(Courses).where(Courses.deleted_at.is_(None))
        )
        return result.scalars().all()

    async def create_course_async(self, title: str, instructor_id) -> Courses:
        course = Courses(title=title, instructor_id=instructor_id)
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return course
```

> **Rules**:
>
> - Tất cả methods async phải có suffix `_async` (vd: `get_courses_async`)
> - Inject DB qua `Depends(get_session)` trong `__init__`
> - Không dùng `session.query()` — chỉ dùng `select()` từ SQLAlchemy 2.0 style

---

### Bước 3 — Controller (API Endpoint)

**File**: `app/api/v1/<domain>/<feature>.py`

```python
from fastapi import APIRouter, Depends

from uuid import UUID

from app.core.deps import AuthorizationService
from app.schemas.<domain>.<feature> import CourseResponse, CreateCourseRequest
from app.services.<domain>.<feature> import CourseService

router = APIRouter(prefix="/<domain>/<feature>", tags=["DOMAIN FEATURE"])

@router.get("", response_model=list[CourseResponse])
async def get_courses(
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: CourseService = Depends(CourseService),
):
    user = await authorization.require_role(["LECTURER"])
    return await service.get_courses_async()

@router.post("", response_model=CourseResponse)
async def create_course(
    body: CreateCourseRequest,
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: CourseService = Depends(CourseService),
):
    user = await authorization.require_role(["LECTURER"])
    return await service.create_course_async(body.title, user.id)
```

> **Rules**:
>
> - Luôn inject `AuthorizationService` trước `service` trong params
> - `require_role` trả về `User` object — dùng `user.id` để lấy current user ID
> - Prefix URL: lowercase + hyphen (vd: `/admin/course-review`)
> - Tags: UPPERCASE (vd: `["ADMIN COURSE"]`)

---

### Bước 4 — Đăng ký Router

**File**: `app/main.py`

```python
from app.api.v1.<domain> import <feature> as <alias>

app.include_router(<alias>.router, prefix=prefix)
```

> `prefix = "/api/v1"` đã được khai báo sẵn ở đầu `main.py`.

---

## 🔐 Authentication & Authorization

### Cơ chế Auth

- Token lưu trong **cookie** tên `access_token` (không dùng Bearer header)
- Cookie được set khi login, Swagger phải bật `withCredentials: true`
- `AuthorizationService` đọc cookie từ request context

### Pattern sử dụng

```python
# Yêu cầu đăng nhập + role cụ thể
user = await authorization.require_role(["ADMIN"])

# Yêu cầu đăng nhập, bất kỳ role
user = await authorization.require_role()

# Không bắt buộc login (public + có thể có user context)
user = await authorization.get_current_user_if_any()  # trả None nếu chưa login
```

### Roles hệ thống

| Role       | Mô tả                           |
| ---------- | ------------------------------- |
| `ADMIN`    | Quản trị viên toàn hệ thống     |
| `LECTURER` | Giảng viên — tạo & bán khóa học |
| `USER`     | Học viên — mua & học khóa học   |

### WebSocket Auth

```python
user = await AuthorizationService.get_require_role_ws(
    websocket,
    required_roles=["USER"]  # None nếu không cần role
)
```

> WS auth ưu tiên: query param `?token=` → header `authorization` → cookie `access_token`

---

## 📊 Database Query Patterns

> **Quan trọng**: Chỉ dùng **SQLAlchemy 2.0 async style**. Không dùng `session.query()`.

```python
from sqlalchemy import select, func, and_, or_
from app.db.models.database import User, Courses

# ── SELECT ONE ──
user = await self.db.scalar(
    select(User).where(User.id == user_id)
)

# ── SELECT MANY ──
result = await self.db.execute(
    select(Courses)
    .where(Courses.is_published == True, Courses.deleted_at.is_(None))
    .order_by(Courses.created_at.desc())
    .limit(10)
)
courses = result.scalars().all()

# ── COUNT ──
total = await self.db.scalar(
    select(func.count(Courses.id))
    .where(Courses.instructor_id == instructor_id)
)

# ── AGGREGATE ──
total_revenue = await self.db.scalar(
    select(func.sum(Transactions.amount))
    .where(Transactions.status == "completed")
)

# ── CREATE ──
item = MyModel(field1=value1, field2=value2)
self.db.add(item)
await self.db.commit()
await self.db.refresh(item)

# ── UPDATE ──
obj = await self.db.scalar(select(MyModel).where(...))
obj.field = new_value
await self.db.commit()

# ── SOFT DELETE ──
from app.libs.formats.datetime import now as get_now
obj.deleted_at = await to_utc_naive(get_now())
await self.db.commit()

# ── EAGER LOAD relationship ──
from sqlalchemy.orm import selectinload
stmt = (
    select(User)
    .where(User.id == user_id)
    .options(selectinload(User.user_roles).selectinload(UserRoles.role))
)
```

---

## 🗄️ Database Entities (Models)

Tất cả entities nằm trong `app/db/models/database.py`. Dưới đây là các entity chính:

### Core Entities

| Entity      | Table               | Mô tả                                    |
| ----------- | ------------------- | ---------------------------------------- |
| `User`      | `public.user`       | Người dùng (USER / LECTURER đều là User) |
| `Role`      | `public.role`       | Định nghĩa vai trò                       |
| `UserRoles` | `public.user_roles` | Bảng liên kết User ↔ Role (many-to-many) |

### Khóa học

| Entity           | Table                    | Mô tả                                                              |
| ---------------- | ------------------------ | ------------------------------------------------------------------ |
| `Categories`     | `public.categories`      | Danh mục (cây, parent/child)                                       |
| `Topics`         | `public.topics`          | Chủ đề con của category                                            |
| `Courses`        | `public.courses`         | Khóa học (approval_status: pending/approved/rejected)              |
| `CourseSections` | `public.course_sections` | Chương/phần của khóa học                                           |
| `Lessons`        | `public.lessons`         | Bài học (lesson_type: video/article/quiz/code/assignment/resource) |
| `LessonVideos`   | -                        | Metadata video của bài học                                         |
| `LessonCodes`    | -                        | Code exercise của bài học                                          |
| `LessonQuizzes`  | -                        | Quiz bài học                                                       |
| `LessonChunks`   | -                        | Chunks RAG của bài học                                             |
| `ResourceChunks` | -                        | Chunks RAG từ tài liệu đính kèm                                    |

### Học tập & Tương tác

| Entity              | Table                       | Mô tả                                             |
| ------------------- | --------------------------- | ------------------------------------------------- |
| `CourseEnrollments` | `public.course_enrollments` | Học viên đăng ký khóa học                         |
| `CourseReviews`     | `public.course_reviews`     | Đánh giá khóa học (rating 1–5)                    |
| `CourseFavourites`  | `public.course_favourites`  | Khóa học yêu thích                                |
| `CourseViews`       | `public.course_views`       | Lượt xem                                          |
| `LessonProgress`    | -                           | Tiến độ học bài                                   |
| `LessonActive`      | -                           | Bài học đang học dở (1 user, 1 course → 1 record) |
| `LessonNotes`       | -                           | Ghi chú của học viên                              |
| `LessonComments`    | -                           | Bình luận bài học                                 |

### Tài chính

| Entity               | Table                        | Mô tả                                       |
| -------------------- | ---------------------------- | ------------------------------------------- |
| `Transactions`       | `public.transactions`        | Lịch sử giao dịch                           |
| `PurchaseItems`      | `public.purchase_items`      | Chi tiết đơn mua khóa học                   |
| `Wallets`            | `public.wallets`             | Ví người dùng (1 user = 1 ví)               |
| `PlatformWallets`    | `public.platform_wallets`    | Ví của nền tảng                             |
| `InstructorEarnings` | `public.instructor_earnings` | Thu nhập giảng viên (hold → pending → paid) |
| `WithdrawalRequests` | `public.withdrawal_requests` | Yêu cầu rút tiền của giảng viên             |
| `Discounts`          | `public.discounts`           | Mã giảm giá                                 |
| `DiscountTargets`    | `public.discount_targets`    | Áp dụng discount cho course/category        |
| `DiscountHistory`    | `public.discount_history`    | Lịch sử dùng mã giảm giá                    |

### Platform

| Entity                  | Table                      | Mô tả                                             |
| ----------------------- | -------------------------- | ------------------------------------------------- |
| `PlatformSettings`      | `public.platform_settings` | Cấu hình nền tảng (platform_fee, hold_days, v.v.) |
| `PlatformWalletHistory` | -                          | Lịch sử biến động ví nền tảng                     |
| `Notifications`         | `public.notifications`     | Thông báo hệ thống                                |
| `SupportedLanguages`    | -                          | Ngôn ngữ lập trình được hỗ trợ (dùng cho Piston)  |

### AI / Chat

| Entity                 | Table | Mô tả                                    |
| ---------------------- | ----- | ---------------------------------------- |
| `TutorChatThreads`     | -     | Thread chat với AI Tutor                 |
| `TutorChatMessages`    | -     | Tin nhắn trong thread                    |
| `TutorChatImages`      | -     | Hình ảnh trong chat                      |
| `LessonTutorMemory`    | -     | Bộ nhớ AI tutor theo bài học             |
| `UserEmbeddingHistory` | -     | Lịch sử embedding preferences người dùng |

### Key Fields trên User

```python
# User đóng vai LECTURER khi có role LECTURER trong UserRoles
user.user_roles  # → list[UserRoles] → UserRoles.role.role_name

# Stats denormalized (cached)
user.course_count        # Số khóa học của giảng viên
user.student_count       # Số học viên của giảng viên
user.rating_avg          # Rating trung bình

# Soft delete
user.deleted_at          # None = còn active

# Vector embedding
user.preferences_embedding  # VECTOR(1536) - sở thích học tập
```

### Key Fields trên Courses

```python
course.approval_status   # "pending" | "approved" | "rejected"
course.is_published      # True = học viên có thể thấy
course.deleted_at        # Soft delete
course.embedding         # VECTOR(1536) - semantic search
course.search_tsv        # TSVECTOR - full-text search
course.level             # "beginner" | "intermediate" | "advanced" | "all"
course.base_price        # Giá gốc (VND)
```

---

## 📋 Naming Conventions

| Item              | Convention         | Ví dụ                                   |
| ----------------- | ------------------ | --------------------------------------- |
| Tên file          | snake_case         | `user_service.py`                       |
| Tên class         | PascalCase         | `UserService`                           |
| Tên method thường | snake_case         | `get_user`                              |
| Tên method async  | suffix `_async`    | `get_user_async`, `create_course_async` |
| Route prefix      | lowercase + hyphen | `/admin/course-review`                  |
| Router tags       | UPPERCASE          | `["ADMIN COURSE"]`                      |
| Tên biến          | snake_case         | `course_id`, `instructor_id`            |
| Enum values       | UPPERCASE          | `"ADMIN"`, `"LECTURER"`                 |

---

## ⚙️ Settings & Environment

**File**: `app/core/settings.py` — dùng `pydantic-settings` đọc từ `.env`

```python
from app.core.settings import settings

settings.DATABASE_ASYNC_URL   # asyncpg connection URL
settings.SECRET_KEY            # JWT secret
settings.GOOGLE_API_KEY        # Gemini API key
settings.PISTON_URL            # Code execution sandbox URL
settings.PAYPAL_CLIENT_ID      # PayPal credentials
settings.FRONTEND_URL          # URL frontend (dùng cho CORS/email links)
```

**Biến môi trường quan trọng trong `.env`**:

```env
DATABASE_ASYNC_URL=postgresql+asyncpg://user:pass@host/dbname
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=10080

GOOGLE_API_KEY=...
GOOGLE_API_KEY_CHAT=...
GOOGLE_CREDENTIALS_PATH=path/to/service-account.json
GOOGLE_ROOT_FOLDER_ID=...

PISTON_URL=http://localhost:4000

PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com

MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_FROM=...
MAIL_SERVER=smtp.gmail.com

FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

---

## 🔒 Security Service

**File**: `app/core/security.py`

```python
security = SecurityService()

# JWT
token = await security.create_access_token(sub=str(user.id))
payload = await security.decode_access_token(token)

# Password
hashed = await SecurityService.hash_password("plaintext")
is_valid = await SecurityService.verify_password("plaintext", hashed)

# OTP (6 chữ số)
otp = await SecurityService.generate_otp()
```

---

## 🗓️ Datetime Utilities

**File**: `app/libs/formats/datetime.py`

```python
from app.libs.formats.datetime import now, now_tzinfo, to_utc_naive

now()           # datetime hiện tại (có timezone)
now_tzinfo()    # tương tự, dùng trong JWT payload
to_utc_naive(dt)  # chuyển datetime → UTC naive (lưu vào PostgreSQL)
```

> **Quan trọng**: Luôn dùng `to_utc_naive()` trước khi gán timestamp vào SQLAlchemy model.

---

## 🌐 AI & Embedding

### Gemini LLM

**File**: `app/core/llm.py`

```python
# Dùng Gemini để generate text
from app.core.llm import get_llm

llm = get_llm()
response = await llm.ainvoke("Your prompt here")
```

### Vector Embedding

**File**: `app/core/embedding.py`

```python
# Tạo embedding từ text để lưu vào pgvector
from app.core.embedding import get_embedding

vector = await get_embedding("text to embed")
# vector là list[float] length=1536, lưu vào VECTOR(1536) column
```

### Các Entity có Embedding

- `Courses.embedding` — semantic search khóa học
- `Topics.embedding` — semantic search chủ đề
- `Lessons.embedding` — semantic search bài học
- `CourseReviews.embedding` — phân tích cảm xúc
- `User.preferences_embedding` — recommendation cá nhân hóa
- `LessonChunks` / `ResourceChunks` — RAG cho AI Tutor

---

## 📬 Request Context (Middleware)

**File**: `app/core/context.py` + `app/middleware/request_context.py`

```python
# Lấy request hiện tại từ bất kỳ đâu (không cần truyền qua params)
from app.core.context import get_request

request = get_request()
token = request.cookies.get("access_token")
```

> Middleware `RequestContextMiddleware` inject request vào `contextvars.ContextVar`
> để các service có thể truy cập mà không cần FastAPI `Depends(Request)`.

---

## 🔌 WebSocket Manager

**File**: `app/core/ws_manager.py`

```python
from app.core.ws_manager import ws_manager

# Gửi message đến user cụ thể qua WebSocket
await ws_manager.send_personal_message(message, user_id)

# Broadcast
await ws_manager.broadcast(message)
```

---

## ⏱️ Scheduler (APScheduler)

**File**: `app/core/scheduler.py`

```python
from app.core.scheduler import scheduler

# Thêm job mới
scheduler.add_job(
    my_function,
    trigger="cron",
    hour=0, minute=0,    # chạy lúc 00:00 mỗi ngày
    id="my_job_id",
    replace_existing=True,
)
```

> Scheduler được khởi động trong `lifespan()` của `main.py`.

---

## 🐳 Docker

**File**: `docker-compose.yaml`

```yaml
# Chỉ có PostgreSQL (với pgvector)
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: studynest_db
    ports:
      - "5433:5432"
```

> PostgreSQL chạy qua Docker trên port **5433**. Các service khác (như Piston) hiện không được cấu hình trong compose này.

---

## 🚀 Chạy Dự Án

### Backend Commands (studynest_be)
- Install dependencies: `pip install -r requirements.txt`
- Run dev server: `uvicorn app.main:app --reload`
- Generate models from DB: `./gen_models.sh` (hoặc `python -m sqlacodegen 'postgresql://admin:StrongPass2026!@127.0.0.1:5433/studynest' --schema public --outfile app/db/models/database.py`)
- Database migrations (Alembic):
  - Create migration: `alembic revision --autogenerate -m "description"`
  - Apply migrations: `alembic upgrade head`

```bash
# 1. Tạo và kích hoạt virtual env
python -m venv .venv
source .venv/bin/activate

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env từ mẫu (xem phần Settings ở trên)

# 4. Chạy Piston API (nếu cần code execution)
docker-compose up -d

# 5. Chạy server
uvicorn app.main:app --reload --port 8000

# Swagger UI: http://localhost:8000/docs
```

---

## ✅ Checklist Khi Viết Code Mới

- [ ] Schema có `model_config = {"from_attributes": True}` nếu là response
- [ ] Method async có suffix `_async`
- [ ] Inject `AuthorizationService` trước service trong controller params
- [ ] Gọi `await authorization.require_role([...])` đầu tiên trong handler
- [ ] Dùng `select()` + `await db.scalar/execute()` — không dùng `session.query()`
- [ ] Soft delete: set `deleted_at` thay vì xóa thật
- [ ] Timestamp lưu DB: dùng `to_utc_naive()` trước khi gán
- [ ] Import entity từ `app.db.models.database`
- [ ] Đăng ký router trong `app/main.py` sau khi tạo xong
- [ ] URL prefix: lowercase + hyphen, tags: UPPERCASE

---

> **Lưu ý cuối**: Project này theo kiến trúc **3-layer rõ ràng** (Controller → Service → DB).
> Không để business logic trong controller, không query DB trực tiếp trong controller.
