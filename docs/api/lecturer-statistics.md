# 📊 Lecturer Statistics API Documentation

Tài liệu hướng dẫn tích hợp API thống kê dành cho Frontend Developer (Lecturer Dashboard).

Base URL: `/api/v1/lecturer/statistics`

---

## 1. Lấy chỉ số tổng quan (Dashboard Overview)

Lấy các chỉ số KPI quan trọng nhất để hiển thị ở cards đầu trang Dashboard.

- **URL**: `GET /api/v1/lecturer/statistics/overview`
- **Auth**: Required (`Bearer <access_token>`)
- **Role**: `LECTURER`

### Response Example

```json
{
  "total_revenue": 150000000.0,
  "total_students": 1250,
  "total_courses": 5,
  "average_rating": 4.8,
  "total_reviews": 320,
  "this_month_revenue": 12000000.0,
  "last_month_revenue": 10000000.0,
  "revenue_growth": 20.0
}
```

### TypeScript Interface

```typescript
export interface LecturerOverview {
  total_revenue: number;
  total_students: number;
  total_courses: number;
  average_rating: number;
  total_reviews: number;
  this_month_revenue: number;
  last_month_revenue: number;
  revenue_growth: number;
}
```

---

## 2. Dữ liệu Biểu đồ Doanh thu (Revenue Chart)

Lấy dữ liệu để vẽ biểu đồ đường (Line Chart) hoặc cột (Bar Chart) thể hiện doanh thu theo thời gian.

- **URL**: `GET /api/v1/lecturer/statistics/revenue-chart`
- **Auth**: Required
- **Params**:
  - `period`: `month` (mặc định - 30 ngày) | `year` (12 tháng gần nhất)

### Example Request

`GET /api/v1/lecturer/statistics/revenue-chart?period=month`

### Response Example

```json
[
  {
    "date": "2024-01-01",
    "revenue": 5000000.0,
    "courses_sold": 10
  },
  {
    "date": "2024-01-02",
    "revenue": 2500000.0,
    "courses_sold": 5
  }
]
```

### TypeScript Interface

```typescript
export interface RevenueChartItem {
  date: string; // "YYYY-MM-DD" (month) or "YYYY-MM" (year)
  revenue: number;
  courses_sold: number;
}
```

---

## 3. Thống kê Hiệu suất Khóa học (Course Performance)

Danh sách các khóa học của giảng viên kèm theo các chỉ số hiệu suất để so sánh.

- **URL**: `GET /api/v1/lecturer/statistics/courses`
- **Auth**: Required
- **Params**:
  - `limit`: `10` (mặc định)

### Response Example

```json
[
  {
    "course_id": "123e4567-e89b-12d3-a456-426614174000",
    "title": "ReactJS Ultimate Guide 2024",
    "thumbnail": "https://example.com/image.jpg",
    "status": "published",
    "revenue": 50000000.0,
    "total_students": 500,
    "average_rating": 4.9,
    "reviews_count": 120,
    "this_month_revenue": 2000000.0
  }
]
```

### TypeScript Interface

```typescript
export interface CoursePerformanceItem {
  course_id: string;
  title: string;
  thumbnail: string | null;
  status: string;
  revenue: number;
  total_students: number;
  average_rating: number;
  reviews_count: number;
  this_month_revenue: number;
}
```

---

## 4. Phân tích Học viên (Student Analytics)

Thống kê về số lượng học viên mới và phân bố học viên theo khóa học.

- **URL**: `GET /api/v1/lecturer/statistics/students`
- **Auth**: Required
- **Params**:
  - `days`: `30` (mặc định) - Số ngày gần nhất để đếm học viên mới.

### Response Example

```json
{
  "total_new_students": 50,
  "active_students": 120,
  "retention_rate": 85.5,
  "students_by_course": [
    { "course_id": "...", "course_title": "ReactJS", "count": 30 },
    { "course_id": "...", "course_title": "NodeJS", "count": 20 }
  ]
}
```

### TypeScript Interface

```typescript
export interface StudentsByCourseItem {
  course_id: string;
  course_title: string;
  count: number;
}

export interface StudentAnalyticsResponse {
  total_new_students: number;
  active_students: number;
  retention_rate: number;
  students_by_course: StudentsByCourseItem[];
}
```

---

## Ghi chú cho Frontend

- **Hiển thị tiền tệ:** Sử dụng `revenue.toLocaleString('vi-VN') + ' VND'` để format tiền tệ.
- **Biểu đồ:**
  - Dùng `RevenueChartItem` cho trục X là `date`, trục Y là `revenue`.
  - Có thể thêm tooltip hiển thị `courses_sold`.
- **Growth:**
  - `revenue_growth` là số phần trăm (%). Nếu dương hiển thị màu xanh (tăng), âm hiển thị màu đỏ (giảm).
