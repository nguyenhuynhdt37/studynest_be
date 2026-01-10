# StudyNest Backend - Cấu Trúc Dự Án

## 📁 Tổng Quan Thư Mục

```
app/
├── api/v1/                 # Controllers (Endpoints)
│   ├── admin/              # Admin APIs
│   ├── lecturer/           # Lecturer APIs
│   ├── user/               # User APIs
│   ├── shares/             # Shared APIs (auth, upload, ...)
│   └── chat/               # Chat/AI APIs
│
├── services/               # Business Logic
│   ├── admin/              # Admin Services
│   ├── lecturer/           # Lecturer Services
│   ├── shares/             # Shared Services
│   └── user/               # User Services
│
├── schemas/                # DTOs (Pydantic Models)
│   ├── admin/              # Admin Schemas
│   ├── auth/               # Auth Schemas
│   ├── lecturer/           # Lecturer Schemas
│   ├── user/               # User Schemas
│   └── shares/             # Shared Schemas
│
├── db/models/              # SQLAlchemy Models
│   └── database.py         # All entity definitions
│
├── core/                   # Core utilities
│   ├── deps.py             # Dependency Injection
│   ├── settings.py         # App Settings
│   └── security.py         # Auth/JWT
│
├── middleware/             # Custom Middlewares
├── libs/                   # Shared libraries
└── main.py                 # App entry point
```

---

## 🔧 Pattern Chuẩn Khi Tạo Feature Mới

### 1. Tạo Schema (DTO)

📍 **File**: `app/schemas/<domain>/<feature>.py`

```python
from pydantic import BaseModel

class MyResponse(BaseModel):
    id: int
    name: str
```

### 2. Tạo Service

📍 **File**: `app/services/<domain>/<feature>.py`

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_session

class MyService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def my_method_async(self) -> dict:
        # Business logic here
        return {"result": "ok"}
```

### 3. Tạo Controller

📍 **File**: `app/api/v1/<domain>/<feature>.py`

```python
from fastapi import APIRouter, Depends
from app.core.deps import AuthorizationService
from app.services.<domain>.<feature> import MyService
from app.schemas.<domain>.<feature> import MyResponse

router = APIRouter(prefix="/<domain>/<feature>", tags=["DOMAIN FEATURE"])

@router.get("", response_model=MyResponse)
async def get_something(
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: MyService = Depends(MyService),
):
    await authorization.require_role(["ADMIN"])  # hoặc ["LECTURER"], ["USER"]
    return await service.my_method_async()
```

### 4. Register Router

📍 **File**: `app/main.py`

```python
# Import
from app.api.v1.<domain> import <feature> as <alias>

# Register
app.include_router(<alias>.router, prefix=prefix)
```

---

## 🔐 Authorization Pattern

```python
from app.core.deps import AuthorizationService

@router.get("/protected")
async def protected_route(
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    # Require specific role(s)
    user = await authorization.require_role(["ADMIN"])

    # user object contains logged-in user info
    return {"user_id": user.id}
```

**Available Roles**: `ADMIN`, `LECTURER`, `USER`

---

## 📊 Database Query Pattern

```python
from sqlalchemy import select, func
from app.db.models.database import User, Courses

# Count
total = await self.db.scalar(
    select(func.count(User.id)).where(User.deleted_at.is_(None))
)

# Select one
user = await self.db.scalar(
    select(User).where(User.id == user_id)
)

# Select many
result = await self.db.execute(
    select(Courses).where(Courses.is_published == True).limit(10)
)
courses = result.scalars().all()

# Aggregation
total_revenue = await self.db.scalar(
    select(func.sum(Transactions.amount)).where(
        Transactions.status == "completed"
    )
)
```

---

## 📋 Naming Conventions

| Item           | Convention         | Example             |
| -------------- | ------------------ | ------------------- |
| File names     | snake_case         | `user_service.py`   |
| Class names    | PascalCase         | `UserService`       |
| Function names | snake_case         | `get_users_async`   |
| Async methods  | suffix `_async`    | `create_user_async` |
| Route prefix   | lowercase + hyphen | `/admin/users`      |
| Router tags    | UPPERCASE          | `["ADMIN USER"]`    |

---

## 🚀 Quick Start: Tạo API Mới

1. **Schema**: `app/schemas/admin/my_feature.py`
2. **Service**: `app/services/admin/my_feature.py`
3. **Controller**: `app/api/v1/admin/my_feature.py`
4. **Register**: Thêm import và `include_router` vào `main.py`

---

## 📝 Example: Admin Statistics Module

### Files Created

- `app/schemas/admin/statistics.py` - Response DTOs
- `app/services/admin/statistics.py` - Business logic
- `app/api/v1/admin/statistics.py` - Endpoints

### Endpoints

```
GET /api/v1/admin/statistics/overview
GET /api/v1/admin/statistics/revenue
GET /api/v1/admin/statistics/revenue/by-category
GET /api/v1/admin/statistics/users
GET /api/v1/admin/statistics/courses
GET /api/v1/admin/statistics/courses/top
GET /api/v1/admin/statistics/instructors
GET /api/v1/admin/statistics/instructors/top
GET /api/v1/admin/statistics/finance
GET /api/v1/admin/statistics/activity
```

---

> **Lưu ý**: Luôn tuân thủ các patterns trên để đảm bảo tính nhất quán của codebase.
