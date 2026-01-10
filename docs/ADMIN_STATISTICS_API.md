# Admin Statistics API - Hướng Dẫn Cho Frontend

## 🔐 Authentication

Tất cả endpoints yêu cầu **đăng nhập với role ADMIN**.
Cookie `access_token` phải được gửi kèm.

---

## 📊 Endpoints

### 1. Overview (Tổng quan Dashboard)

```
GET /api/v1/admin/statistics/overview
```

**Response:**

```typescript
interface OverviewResponse {
  total_users: number;
  total_courses: number;
  total_instructors: number;
  total_revenue: number; // VND
  today_revenue: number;
  pending_withdrawals: number;
  pending_refunds: number;
}
```

---

### 2. Revenue Stats (Biểu đồ doanh thu)

```
GET /api/v1/admin/statistics/revenue?period=month&from_date=2026-01-01&to_date=2026-12-31
```

**Query Params:**
| Param | Type | Default | Mô tả |
|-------|------|---------|-------|
| `period` | `day\|week\|month\|year` | `month` | Nhóm theo |
| `from_date` | `YYYY-MM-DD` | Auto | Ngày bắt đầu |
| `to_date` | `YYYY-MM-DD` | Today | Ngày kết thúc |

**Response:**

```typescript
interface RevenueStatsResponse {
  total: number;
  platform_income: number;
  instructor_payout: number;
  data: Array<{
    date: string; // YYYY-MM-DD
    amount: number;
    count: number;
  }>;
}
```

---

### 3. Revenue by Category (Pie chart)

```
GET /api/v1/admin/statistics/revenue/by-category
```

**Response:**

```typescript
interface RevenueByCategoryResponse {
  data: Array<{
    category_id: string;
    category_name: string;
    revenue: number;
    percentage: number; // 0-100
  }>;
}
```

---

### 4. User Stats

```
GET /api/v1/admin/statistics/users?period=month
```

**Response:**

```typescript
interface UserStatsResponse {
  total: number;
  verified: number;
  banned: number;
  by_role: Array<{ role: string; count: number }>;
  growth: Array<{
    date: string;
    new_users: number;
    active_users: number;
  }>;
}
```

---

### 5. Course Stats

```
GET /api/v1/admin/statistics/courses
```

**Response:**

```typescript
interface CourseStatsResponse {
  total: number;
  by_status: {
    published: number;
    draft: number;
    archived: number;
  };
  by_level: {
    beginner: number;
    intermediate: number;
    advanced: number;
    all: number;
  };
  avg_rating: number;
  total_enrollments: number;
}
```

---

### 6. Top Courses

```
GET /api/v1/admin/statistics/courses/top?sort_by=revenue&limit=10
```

**Query Params:**
| Param | Type | Default | Options |
|-------|------|---------|---------|
| `sort_by` | string | `revenue` | `revenue\|views\|enrollments` |
| `limit` | number | 10 | 1-50 |

**Response:**

```typescript
interface TopCoursesResponse {
  data: Array<{
    course_id: string;
    title: string;
    instructor_name: string;
    thumbnail: string | null;
    value: number;
    metric: string;
  }>;
}
```

---

### 7. Instructor Stats

```
GET /api/v1/admin/statistics/instructors
```

**Response:**

```typescript
interface InstructorStatsResponse {
  total: number;
  total_earnings: number;
  pending_payout: number;
  paid_out: number;
}
```

---

### 8. Top Instructors

```
GET /api/v1/admin/statistics/instructors/top?sort_by=revenue&limit=10
```

**Query Params:**
| Param | Type | Default | Options |
|-------|------|---------|---------|
| `sort_by` | string | `revenue` | `revenue\|students\|courses` |
| `limit` | number | 10 | 1-50 |

**Response:**

```typescript
interface TopInstructorsResponse {
  data: Array<{
    instructor_id: string;
    name: string;
    avatar: string | null;
    value: number;
    metric: string;
    courses_count: number;
    students_count: number;
  }>;
}
```

---

### 9. Finance Stats

```
GET /api/v1/admin/statistics/finance
```

**Response:**

```typescript
interface FinanceStatsResponse {
  platform_balance: number;
  total_deposits: number;
  total_withdrawals: number;
  pending_withdrawals: {
    count: number;
    amount: number;
  };
  refunds: {
    requested: number;
    approved: number;
    rejected: number;
    total_refunded: number;
  };
}
```

---

### 10. Activity Stats

```
GET /api/v1/admin/statistics/activity?period=month
```

**Response:**

```typescript
interface ActivityStatsResponse {
  lesson_views: number;
  lesson_completions: number;
  comments: number;
  notes_created: number;
  quiz_attempts: number;
}
```

---

## 🛠️ Axios Example

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_URL_BACKEND,
  withCredentials: true, // ⚠️ BẮT BUỘC để gửi cookie
});

// Lấy overview
const { data } = await api.get("/api/v1/admin/statistics/overview");

// Lấy revenue với filter
const { data } = await api.get("/api/v1/admin/statistics/revenue", {
  params: { period: "week" },
});

// Top courses theo views
const { data } = await api.get("/api/v1/admin/statistics/courses/top", {
  params: { sort_by: "views", limit: 5 },
});
```

---

## 📈 Suggested Charts

| Endpoint               | Chart Type         |
| ---------------------- | ------------------ |
| `/overview`            | Stat Cards         |
| `/revenue`             | Line/Area Chart    |
| `/revenue/by-category` | Pie/Donut Chart    |
| `/users` (growth)      | Line Chart         |
| `/courses` (by_status) | Pie Chart          |
| `/courses/top`         | Bar Chart / Table  |
| `/instructors`         | Stat Cards         |
| `/instructors/top`     | Table              |
| `/finance`             | Stat Cards + Table |

---

## ⚠️ Error Responses

```json
// 401 - Chưa đăng nhập
{ "detail": "Token not found in cookies" }

// 403 - Không có quyền ADMIN
{ "detail": "Bạn không có quyền truy cập." }
```
