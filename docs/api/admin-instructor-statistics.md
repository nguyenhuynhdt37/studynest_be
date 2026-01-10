# 📊 API Thống kê Giảng viên (Admin)

> **Base URL**: `/api/admin/statistics`  
> **Auth**: Bearer Token (Role: ADMIN)

---

## 1. Thống kê tổng quan giảng viên

### Endpoint

```
GET /admin/statistics/instructors
```

### Input (Query Params)

Không có params.

### Output

```typescript
{
  total: number; // Tổng số giảng viên
  total_earnings: number; // Tổng thu nhập (VND)
  pending_payout: number; // Số tiền chờ thanh toán
  paid_out: number; // Số tiền đã thanh toán
}
```

### Ví dụ Response

```json
{
  "total": 45,
  "total_earnings": 150000000,
  "pending_payout": 25000000,
  "paid_out": 125000000
}
```

---

## 2. Top giảng viên

### Endpoint

```
GET /admin/statistics/instructors/top
```

### Input (Query Params)

| Param     | Type   | Default     | Mô tả                                                  |
| --------- | ------ | ----------- | ------------------------------------------------------ |
| `sort_by` | string | `"revenue"` | Tiêu chí sắp xếp: `revenue` \| `students` \| `courses` |
| `limit`   | number | `10`        | Số lượng kết quả (1-50)                                |

### Output

```typescript
{
  data: Array<{
    instructor_id: string; // UUID
    name: string;
    avatar: string | null;
    value: number; // Giá trị theo tiêu chí sắp xếp
    metric: string; // "revenue" | "students" | "courses"
    courses_count: number; // Số khóa học
    students_count: number; // Số học viên
  }>;
}
```

### Ví dụ Request

```
GET /admin/statistics/instructors/top?sort_by=revenue&limit=5
```

### Ví dụ Response

```json
{
  "data": [
    {
      "instructor_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Nguyễn Văn A",
      "avatar": "https://storage.example.com/avatar1.jpg",
      "value": 50000000,
      "metric": "revenue",
      "courses_count": 5,
      "students_count": 320
    },
    {
      "instructor_id": "550e8400-e29b-41d4-a716-446655440002",
      "name": "Trần Thị B",
      "avatar": null,
      "value": 35000000,
      "metric": "revenue",
      "courses_count": 3,
      "students_count": 180
    }
  ]
}
```

---

## 3. Biểu đồ tăng trưởng giảng viên

### Endpoint

```
GET /admin/statistics/instructors/growth
```

### Input (Query Params)

| Param    | Type   | Default   | Mô tả                                                 |
| -------- | ------ | --------- | ----------------------------------------------------- |
| `period` | string | `"month"` | `day` = 30 ngày gần nhất, `month` = 12 tháng gần nhất |

### Output

```typescript
{
  data: Array<{
    date: string; // "YYYY-MM" hoặc "YYYY-MM-DD"
    new_instructors: number; // Số giảng viên mới
    total_instructors: number; // Tổng cộng dồn
  }>;
  total_new_this_period: number; // Tổng mới trong kỳ
  growth_rate: number; // % tăng trưởng
}
```

### Ví dụ Request

```
GET /admin/statistics/instructors/growth?period=month
```

### Ví dụ Response

```json
{
  "data": [
    { "date": "2024-01", "new_instructors": 3, "total_instructors": 30 },
    { "date": "2024-02", "new_instructors": 5, "total_instructors": 35 },
    { "date": "2024-03", "new_instructors": 2, "total_instructors": 37 }
  ],
  "total_new_this_period": 10,
  "growth_rate": 33.33
}
```

---

## 4. Chi tiết một giảng viên

### Endpoint

```
GET /admin/statistics/instructors/{instructor_id}
```

### Input (Path Params)

| Param           | Type | Mô tả             |
| --------------- | ---- | ----------------- |
| `instructor_id` | UUID | ID của giảng viên |

### Output

```typescript
{
  instructor_id: string;
  name: string;
  email: string;
  avatar: string | null;
  join_date: string; // ISO datetime

  // Thống kê tổng
  total_revenue: number;
  total_students: number;
  total_courses: number;
  average_rating: number; // 0.0 - 5.0

  // 30 ngày gần nhất
  revenue_last_30d: number;
  students_last_30d: number;

  // Trạng thái
  is_active: boolean;
  is_banned: boolean;

  // Top khóa học của giảng viên
  top_courses: Array<{
    course_id: string;
    title: string;
    instructor_name: string;
    thumbnail: string | null;
    value: number;
    metric: string;
  }>;
}
```

### Ví dụ Request

```
GET /admin/statistics/instructors/550e8400-e29b-41d4-a716-446655440001
```

### Ví dụ Response

```json
{
  "instructor_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Nguyễn Văn A",
  "email": "nguyenvana@example.com",
  "avatar": "https://storage.example.com/avatar1.jpg",
  "join_date": "2023-06-15T10:30:00Z",

  "total_revenue": 50000000,
  "total_students": 320,
  "total_courses": 5,
  "average_rating": 4.7,

  "revenue_last_30d": 8500000,
  "students_last_30d": 45,

  "is_active": true,
  "is_banned": false,

  "top_courses": [
    {
      "course_id": "course-uuid-1",
      "title": "Lập trình Python cơ bản",
      "instructor_name": "Nguyễn Văn A",
      "thumbnail": "https://storage.example.com/python.jpg",
      "value": 25000000,
      "metric": "revenue"
    }
  ]
}
```

---

## 5. Doanh thu theo giảng viên

### Endpoint

```
GET /admin/statistics/revenue/by-instructor
```

### Input (Query Params)

| Param       | Type   | Default | Mô tả                      |
| ----------- | ------ | ------- | -------------------------- |
| `from_date` | date   | `null`  | Ngày bắt đầu (YYYY-MM-DD)  |
| `to_date`   | date   | `null`  | Ngày kết thúc (YYYY-MM-DD) |
| `limit`     | number | `20`    | Số lượng kết quả (1-100)   |

### Output

```typescript
{
  total_revenue: number; // Tổng doanh thu
  total_platform_fee: number; // Tổng phí platform
  total_instructor_earning: number; // Tổng giảng viên nhận
  data: Array<{
    instructor_id: string;
    name: string;
    email: string;
    avatar: string | null;
    revenue: number; // Doanh thu
    platform_fee: number; // Phí platform
    net_earning: number; // Thu nhập thực
    transaction_count: number; // Số giao dịch
    courses_sold: number; // Số khóa đã bán
  }>;
}
```

### Ví dụ Request

```
GET /admin/statistics/revenue/by-instructor?from_date=2024-01-01&to_date=2024-03-31&limit=10
```

### Ví dụ Response

```json
{
  "total_revenue": 150000000,
  "total_platform_fee": 22500000,
  "total_instructor_earning": 127500000,
  "data": [
    {
      "instructor_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Nguyễn Văn A",
      "email": "nguyenvana@example.com",
      "avatar": "https://storage.example.com/avatar1.jpg",
      "revenue": 50000000,
      "platform_fee": 7500000,
      "net_earning": 42500000,
      "transaction_count": 125,
      "courses_sold": 5
    }
  ]
}
```

---

## 📝 TypeScript Types (Copy cho FE)

```typescript
// ============ INSTRUCTOR STATS ============
export interface InstructorStatsResponse {
  total: number;
  total_earnings: number;
  pending_payout: number;
  paid_out: number;
}

// ============ TOP INSTRUCTORS ============
export interface TopInstructorItem {
  instructor_id: string;
  name: string;
  avatar: string | null;
  value: number;
  metric: "revenue" | "students" | "courses";
  courses_count: number;
  students_count: number;
}

export interface TopInstructorsResponse {
  data: TopInstructorItem[];
}

export interface GetTopInstructorsParams {
  sort_by?: "revenue" | "students" | "courses";
  limit?: number;
}

// ============ INSTRUCTOR GROWTH ============
export interface InstructorGrowthPoint {
  date: string;
  new_instructors: number;
  total_instructors: number;
}

export interface InstructorGrowthResponse {
  data: InstructorGrowthPoint[];
  total_new_this_period: number;
  growth_rate: number;
}

export interface GetInstructorGrowthParams {
  period?: "day" | "month";
}

// ============ INSTRUCTOR DETAIL ============
export interface TopCourseItem {
  course_id: string;
  title: string;
  instructor_name: string;
  thumbnail: string | null;
  value: number;
  metric: string;
}

export interface InstructorDetailResponse {
  instructor_id: string;
  name: string;
  email: string;
  avatar: string | null;
  join_date: string;
  total_revenue: number;
  total_students: number;
  total_courses: number;
  average_rating: number;
  revenue_last_30d: number;
  students_last_30d: number;
  is_active: boolean;
  is_banned: boolean;
  top_courses: TopCourseItem[];
}

// ============ REVENUE BY INSTRUCTOR ============
export interface InstructorRevenueItem {
  instructor_id: string;
  name: string;
  email: string;
  avatar: string | null;
  revenue: number;
  platform_fee: number;
  net_earning: number;
  transaction_count: number;
  courses_sold: number;
}

export interface RevenueByInstructorResponse {
  total_revenue: number;
  total_platform_fee: number;
  total_instructor_earning: number;
  data: InstructorRevenueItem[];
}

export interface GetRevenueByInstructorParams {
  from_date?: string; // YYYY-MM-DD
  to_date?: string; // YYYY-MM-DD
  limit?: number;
}
```

---

## 🔌 API Service Example (React/Next.js)

```typescript
import { api } from "@/lib/api";

export const instructorStatsApi = {
  // 1. Thống kê tổng quan
  getStats: () =>
    api.get<InstructorStatsResponse>("/admin/statistics/instructors"),

  // 2. Top giảng viên
  getTop: (params?: GetTopInstructorsParams) =>
    api.get<TopInstructorsResponse>("/admin/statistics/instructors/top", {
      params,
    }),

  // 3. Biểu đồ tăng trưởng
  getGrowth: (params?: GetInstructorGrowthParams) =>
    api.get<InstructorGrowthResponse>("/admin/statistics/instructors/growth", {
      params,
    }),

  // 4. Chi tiết giảng viên
  getDetail: (instructorId: string) =>
    api.get<InstructorDetailResponse>(
      `/admin/statistics/instructors/${instructorId}`
    ),

  // 5. Doanh thu theo giảng viên
  getRevenueByInstructor: (params?: GetRevenueByInstructorParams) =>
    api.get<RevenueByInstructorResponse>(
      "/admin/statistics/revenue/by-instructor",
      { params }
    ),

  // 6. Thống kê theo danh mục
  getByCategory: (limitInstructors?: number) =>
    api.get<InstructorByCategoryResponse>(
      "/admin/statistics/instructors/by-category",
      {
        params: { limit_instructors: limitInstructors },
      }
    ),

  // 7. Xuất CSV
  exportCsv: (params?: ExportInstructorParams) => {
    window.open(
      `/api/admin/statistics/instructors/export?${new URLSearchParams(
        params as any
      )}`,
      "_blank"
    );
  },
};
```

---

## 6. Thống kê giảng viên theo danh mục

### Endpoint

```
GET /admin/statistics/instructors/by-category
```

### Input (Query Params)

| Param               | Type   | Default | Mô tả                                 |
| ------------------- | ------ | ------- | ------------------------------------- |
| `limit_instructors` | number | `5`     | Số top giảng viên mỗi danh mục (1-20) |

### Output

```typescript
{
  data: Array<{
    category_id: string; // UUID
    category_name: string;
    instructor_count: number; // Số giảng viên trong danh mục
    total_courses: number; // Số khóa học
    total_revenue: number; // Tổng doanh thu (VND)
    top_instructors: Array<{
      // Top giảng viên theo doanh thu
      instructor_id: string;
      name: string;
      avatar: string | null;
      value: number;
      metric: string;
      courses_count: number;
      students_count: number;
    }>;
  }>;
  total_categories: number;
}
```

### Ví dụ Request

```
GET /admin/statistics/instructors/by-category?limit_instructors=3
```

### Ví dụ Response

```json
{
  "data": [
    {
      "category_id": "cat-uuid-1",
      "category_name": "Lập trình",
      "instructor_count": 15,
      "total_courses": 42,
      "total_revenue": 120000000,
      "top_instructors": [
        {
          "instructor_id": "inst-uuid-1",
          "name": "Nguyễn Văn A",
          "avatar": "https://example.com/avatar1.jpg",
          "value": 45000000,
          "metric": "revenue",
          "courses_count": 5,
          "students_count": 230
        }
      ]
    }
  ],
  "total_categories": 8
}
```

---

## 7. Xuất thống kê giảng viên (CSV)

### Endpoint

```
GET /admin/statistics/instructors/export
```

### Input (Query Params)

| Param       | Type   | Default     | Mô tả                                         |
| ----------- | ------ | ----------- | --------------------------------------------- |
| `sort_by`   | string | `"revenue"` | Sắp xếp: `revenue` \| `students` \| `courses` |
| `from_date` | date   | 1 năm trước | Ngày bắt đầu (YYYY-MM-DD)                     |
| `to_date`   | date   | Hôm nay     | Ngày kết thúc (YYYY-MM-DD)                    |

### Output

File CSV với các cột:

- STT
- ID Giảng viên
- Họ tên
- Email
- Số khóa học
- Số học viên
- Đánh giá
- Tổng doanh thu (VND)

### Ví dụ Request

```
GET /admin/statistics/instructors/export?sort_by=revenue&from_date=2024-01-01&to_date=2024-12-31
```

### Ví dụ sử dụng (FE)

```typescript
// Cách 1: Mở tab mới download
const downloadInstructorCsv = () => {
  const params = new URLSearchParams({
    sort_by: "revenue",
    from_date: "2024-01-01",
    to_date: "2024-12-31",
  });
  window.open(`/api/admin/statistics/instructors/export?${params}`, "_blank");
};

// Cách 2: Dùng fetch với blob
const downloadCsv = async () => {
  const response = await fetch(
    "/api/admin/statistics/instructors/export?sort_by=revenue",
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "instructors.csv";
  a.click();
};
```

---

## 📝 TypeScript Types bổ sung

```typescript
// ============ INSTRUCTOR BY CATEGORY ============
export interface InstructorByCategoryItem {
  category_id: string;
  category_name: string;
  instructor_count: number;
  total_courses: number;
  total_revenue: number;
  top_instructors: TopInstructorItem[];
}

export interface InstructorByCategoryResponse {
  data: InstructorByCategoryItem[];
  total_categories: number;
}

// ============ EXPORT PARAMS ============
export interface ExportInstructorParams {
  sort_by?: "revenue" | "students" | "courses";
  from_date?: string; // YYYY-MM-DD
  to_date?: string; // YYYY-MM-DD
}
```
