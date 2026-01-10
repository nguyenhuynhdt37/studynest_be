# 📊 API Xuất Báo cáo Toàn diện (Admin)

> **Endpoint**: `GET /api/v1/admin/statistics/export/comprehensive`  
> **Auth**: Bearer Token (Role: ADMIN)

---

## Mô tả

API xuất báo cáo toàn diện bao gồm **tất cả thống kê** của hệ thống, hỗ trợ xuất dạng **Excel (XLSX)** hoặc **JSON**.

---

## Input (Query Params)

| Param       | Type   | Default     | Mô tả                            |
| ----------- | ------ | ----------- | -------------------------------- |
| `from_date` | date   | 1 năm trước | Ngày bắt đầu (YYYY-MM-DD)        |
| `to_date`   | date   | Hôm nay     | Ngày kết thúc (YYYY-MM-DD)       |
| `format`    | string | `"xlsx"`    | Định dạng xuất: `xlsx` \| `json` |

---

## Output

### Format: `xlsx` (Excel)

File Excel với **13 sheets**:

| Sheet                | Nội dung                                                |
| -------------------- | ------------------------------------------------------- |
| **Tổng quan**        | Tổng users, courses, instructors, doanh thu             |
| **Doanh thu**        | Tổng doanh thu, thu nhập platform, chi trả giảng viên   |
| **DT theo tháng**    | Doanh thu và số giao dịch theo từng tháng               |
| **DT theo danh mục** | Doanh thu và tỷ lệ % theo từng category                 |
| **Người dùng**       | Tổng users, verified, banned                            |
| **ND theo vai trò**  | Số lượng user theo từng role                            |
| **Khóa học**         | Tổng, published, draft, archived, rating, enrollments   |
| **KH theo cấp độ**   | Số khóa học theo level (Beginner/Intermediate/Advanced) |
| **Top khóa học**     | Top 20 khóa học theo doanh thu                          |
| **Giảng viên**       | Tổng giảng viên, earnings, pending, paid                |
| **Top giảng viên**   | Top 20 giảng viên theo doanh thu                        |
| **Tài chính**        | Số dư platform, deposits, withdrawals, refunds          |
| **Hoạt động**        | Lượt xem, comments, notes, quiz attempts                |

### Format: `json`

```typescript
{
  overview: {
    "Tổng người dùng": number;
    "Tổng khóa học": number;
    "Tổng giảng viên": number;
    "Tổng doanh thu (VND)": number;
    "Doanh thu hôm nay (VND)": number;
    "Yêu cầu rút tiền chờ duyệt": number;
    "Yêu cầu hoàn tiền chờ duyệt": number;
  };

  revenue_summary: {
    "Tổng doanh thu (VND)": number;
    "Thu nhập nền tảng (VND)": number;
    "Chi trả giảng viên (VND)": number;
  };

  revenue_monthly: Array<{
    "Tháng": string;
    "Doanh thu (VND)": number;
    "Số giao dịch": number;
  }>;

  revenue_by_category: Array<{
    "Danh mục": string;
    "Doanh thu (VND)": number;
    "Tỷ lệ (%)": number;
  }>;

  user_summary: {
    "Tổng người dùng": number;
    "Đã xác thực": number;
    "Bị khóa": number;
  };

  users_by_role: Array<{
    "Vai trò": string;
    "Số lượng": number;
  }>;

  course_summary: {
    "Tổng khóa học": number;
    "Đã xuất bản": number;
    "Bản nháp": number;
    "Đã lưu trữ": number;
    "Đánh giá trung bình": number;
    "Tổng số đăng ký": number;
  };

  courses_by_level: Array<{
    "Cấp độ": string;
    "Số lượng": number;
  }>;

  top_courses: Array<{
    "STT": number;
    "Tên khóa học": string;
    "Giảng viên": string;
    "Doanh thu (VND)": number;
  }>;

  instructor_summary: {
    "Tổng giảng viên": number;
    "Tổng thu nhập (VND)": number;
    "Chờ thanh toán (VND)": number;
    "Đã thanh toán (VND)": number;
  };

  top_instructors: Array<{
    "STT": number;
    "Họ tên": string;
    "Số khóa học": number;
    "Số học viên": number;
    "Doanh thu (VND)": number;
  }>;

  finance_summary: {
    "Số dư nền tảng (VND)": number;
    "Tổng nạp tiền (VND)": number;
    "Tổng rút tiền (VND)": number;
    "Yêu cầu rút đang chờ": number;
    "Số tiền rút đang chờ (VND)": number;
    "Hoàn tiền đã yêu cầu": number;
    "Hoàn tiền đã duyệt": number;
    "Hoàn tiền bị từ chối": number;
    "Tổng tiền đã hoàn (VND)": number;
  };

  activity_summary: {
    "Lượt xem bài học": number;
    "Bài học hoàn thành": number;
    "Bình luận": number;
    "Ghi chú tạo mới": number;
    "Lượt làm quiz": number;
  };

  metadata: {
    report_date: string;  // YYYY-MM-DD
    from_date: string;
    to_date: string;
  };
}
```

---

## Ví dụ Request

### Xuất Excel (mặc định)

```
GET /api/v1/admin/statistics/export/comprehensive
```

### Xuất Excel với khoảng thời gian

```
GET /api/v1/admin/statistics/export/comprehensive?from_date=2024-01-01&to_date=2024-12-31
```

### Xuất JSON

```
GET /api/v1/admin/statistics/export/comprehensive?format=json
```

---

## Sử dụng (FE)

### Download Excel

```typescript
const downloadComprehensiveReport = (fromDate?: string, toDate?: string) => {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);

  window.open(
    `/api/v1/admin/statistics/export/comprehensive?${params}`,
    "_blank"
  );
};

// Sử dụng
downloadComprehensiveReport("2024-01-01", "2024-12-31");
```

### Fetch JSON

```typescript
const fetchComprehensiveReport = async (fromDate?: string, toDate?: string) => {
  const params = new URLSearchParams({ format: "json" });
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);

  const response = await api.get(
    `/admin/statistics/export/comprehensive?${params}`
  );
  return response.data;
};
```

---

## TypeScript Types

```typescript
export interface ComprehensiveReportParams {
  from_date?: string; // YYYY-MM-DD
  to_date?: string; // YYYY-MM-DD
  format?: "xlsx" | "json";
}

export interface OverviewStats {
  "Tổng người dùng": number;
  "Tổng khóa học": number;
  "Tổng giảng viên": number;
  "Tổng doanh thu (VND)": number;
  "Doanh thu hôm nay (VND)": number;
  "Yêu cầu rút tiền chờ duyệt": number;
  "Yêu cầu hoàn tiền chờ duyệt": number;
}

export interface ComprehensiveReportResponse {
  overview: OverviewStats;
  revenue_summary: Record<string, number>;
  revenue_monthly: Array<Record<string, string | number>>;
  revenue_by_category: Array<Record<string, string | number>>;
  user_summary: Record<string, number>;
  users_by_role: Array<{ "Vai trò": string; "Số lượng": number }>;
  course_summary: Record<string, number>;
  courses_by_level: Array<{ "Cấp độ": string; "Số lượng": number }>;
  top_courses: Array<Record<string, string | number>>;
  instructor_summary: Record<string, number>;
  top_instructors: Array<Record<string, string | number>>;
  finance_summary: Record<string, number>;
  activity_summary: Record<string, number>;
  metadata: {
    report_date: string;
    from_date: string;
    to_date: string;
  };
}
```

---

## Lưu ý

1. **Excel file**: Tên file có dạng `bao_cao_toan_dien_YYYYMMDD.xlsx`
2. **Styling**: File Excel có header màu xanh, border đầy đủ, auto-fit column width
3. **Encoding**: File Excel hỗ trợ tiếng Việt đầy đủ
4. **Fallback**: Nếu server chưa cài `openpyxl`, API sẽ trả về JSON thay vì lỗi
