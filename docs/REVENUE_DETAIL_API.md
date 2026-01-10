# Revenue Detail API - Hướng Dẫn Frontend

## 🔐 Authentication

Yêu cầu **role ADMIN** + Cookie `access_token`

---

## 📊 Endpoints

### 1. So Sánh Doanh Thu (Compare)

```
GET /api/v1/admin/statistics/revenue/compare
```

**Query Params (Bắt buộc):**
| Param | Type | Mô tả |
|-------|------|-------|
| `current_from` | `YYYY-MM-DD` | Kỳ hiện tại - Bắt đầu |
| `current_to` | `YYYY-MM-DD` | Kỳ hiện tại - Kết thúc |
| `previous_from` | `YYYY-MM-DD` | Kỳ so sánh - Bắt đầu |
| `previous_to` | `YYYY-MM-DD` | Kỳ so sánh - Kết thúc |

**Response:**

```typescript
interface RevenueCompareResponse {
  current: {
    from_date: string;
    to_date: string;
    total: number;
    transaction_count: number;
    platform_income: number;
    instructor_payout: number;
  };
  previous: {
    /* same structure */
  };
  change_amount: number;
  change_percent: number;
}
```

---

### 2. Danh Sách Giao Dịch (Transactions)

```
GET /api/v1/admin/statistics/revenue/transactions
```

**Query Params:**
| Param | Type | Default | Mô tả |
|-------|------|---------|-------|
| `from_date` | date | -30 days | Từ ngày |
| `to_date` | date | today | Đến ngày |
| `status` | string | null | `completed\|pending\|refunded` |
| `page` | int | 1 | Trang |
| `size` | int | 20 | Items/trang (max 100) |

**Response:**

```typescript
interface TransactionsListResponse {
  items: Array<{
    id: string;
    user_id: string;
    user_name: string;
    user_email: string;
    course_id: string | null;
    course_title: string | null;
    amount: number;
    type: string;
    status: string;
    gateway: string | null;
    created_at: string;
  }>;
  total: number;
  page: number;
  size: number;
  pages: number;
}
```

---

### 3. Doanh Thu Theo Giảng Viên

```
GET /api/v1/admin/statistics/revenue/by-instructor
```

**Query Params:**
| Param | Type | Default |
|-------|------|---------|
| `from_date` | date | -365 days |
| `to_date` | date | today |
| `limit` | int | 20 (max 100) |

**Response:**

```typescript
interface RevenueByInstructorResponse {
  total_revenue: number;
  total_platform_fee: number;
  total_instructor_earning: number;
  data: Array<{
    instructor_id: string;
    name: string;
    email: string;
    avatar: string | null;
    revenue: number;
    platform_fee: number;
    net_earning: number;
    transaction_count: number;
    courses_sold: number;
  }>;
}
```

---

### 4. Doanh Thu Theo Khóa Học

```
GET /api/v1/admin/statistics/revenue/by-course
```

**Query Params:** _(Giống by-instructor)_

**Response:**

```typescript
interface RevenueByCourseResponse {
  total_revenue: number;
  total_sales: number;
  data: Array<{
    course_id: string;
    title: string;
    instructor_id: string;
    instructor_name: string;
    thumbnail: string | null;
    revenue: number;
    sales_count: number;
    avg_price: number;
    refund_count: number;
  }>;
}
```

---

### 5. Xu Hướng Doanh Thu (Trends)

```
GET /api/v1/admin/statistics/revenue/trends
```

**Query Params:**
| Param | Type | Default | Options |
|-------|------|---------|---------|
| `period` | string | month | `month\|week` |
| `months` | int | 12 | 1-36 |

**Response:**

```typescript
interface RevenueTrendsResponse {
  data: Array<{
    period: string; // YYYY-MM
    revenue: number;
    growth_rate: number; // %
    transaction_count: number;
  }>;
  avg_monthly_revenue: number;
  avg_growth_rate: number;
  best_month: string | null;
  best_month_revenue: number;
}
```

---

## 🛠️ Axios Example

```typescript
// So sánh tháng này vs tháng trước
const { data } = await api.get("/api/v1/admin/statistics/revenue/compare", {
  params: {
    current_from: "2026-01-01",
    current_to: "2026-01-31",
    previous_from: "2025-12-01",
    previous_to: "2025-12-31",
  },
});

// Danh sách giao dịch
const { data } = await api.get(
  "/api/v1/admin/statistics/revenue/transactions",
  {
    params: { status: "completed", page: 1, size: 10 },
  }
);

// Trends
const { data } = await api.get("/api/v1/admin/statistics/revenue/trends", {
  params: { period: "month", months: 6 },
});
```

---

## 📈 Suggested Charts

| Endpoint         | Chart Type                       |
| ---------------- | -------------------------------- |
| `/compare`       | Comparison Cards + Bar Chart     |
| `/transactions`  | Data Table with Pagination       |
| `/by-instructor` | Bar Chart + Table                |
| `/by-course`     | Bar Chart + Table                |
| `/trends`        | Line Chart với growth indicators |

---

## 6. Export CSV (NEW)

```
GET /api/v1/admin/statistics/revenue/export?group_by=day
```

**Query Params:**
| Param | Type | Default | Options |
|-------|------|---------|---------|
| `group_by` | string | `day` | `day\|month\|year` |
| `from_date` | date | auto | Ngày bắt đầu |
| `to_date` | date | today | Ngày kết thúc |

**Response:** File CSV download

**CSV Columns:**

- `date` / `month` / `year` (tuỳ group_by)
- `platform_income` (Doanh thu nền tảng)
- `instructor_payout` (Phần giảng viên)
- `total_transaction` (Tổng giao dịch)
- `transaction_count` (Số giao dịch)

**Download Example:**

```typescript
const response = await api.get("/api/v1/admin/statistics/revenue/export", {
  params: { group_by: "month" },
  responseType: "blob",
});

const url = window.URL.createObjectURL(new Blob([response.data]));
const a = document.createElement("a");
a.href = url;
a.download = "revenue.csv";
a.click();
```
