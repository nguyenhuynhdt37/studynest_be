# API: Gợi ý khóa học cá nhân hóa

## Endpoint

```
GET /api/v1/courses/feed/recommend
```

## Authentication

- **Yêu cầu:** JWT Bearer Token (trong cookie `access_token`)
- **Không có query params** — user được lấy từ token

---

## Luồng xử lý (Backend)

### 1. Router (`app/api/v1/user/courses.py:22-32`)

```python
@router.get("/feed/recommend")
async def recommend_feed(
    auth: AuthorizationService = Depends(AuthorizationService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):
    user: User = await auth.get_current_user()
    return await course_service.get_recommended_top20(user.id)
```

**Input:**
| Param | Nguồn | Ví dụ |
|---|---|---|
| `user_id` | JWT token → `auth.get_current_user()` | `uuid` |

**Output:** `CoursePublicService.get_recommended_top20()`

---

### 2. Service (`app/services/user/courses.py:1156-1193`)

```python
async def get_recommended_top20(self, user_id: uuid.UUID):
    stmt = select(
        literal_column("course_id"),
        literal_column("course_title"),
        literal_column("course_thumbnail"),
        literal_column("instructor_id"),
        literal_column("instructor_name"),
        literal_column("instructor_avatar"),
        literal_column("course_slug"),
        literal_column("similarity"),
    ).select_from(
        func.fn_recommend_top20(cast(literal_column(f"'{user_id}'"), UUID))
    )
    rows = (await self.db.execute(stmt)).mappings().all()
    return {"items": [...]}
```

**Logic:**
- Gọi **PostgreSQL function** `fn_recommend_top20(user_id)`
- Trả về **tối đa 20 khóa học** được gợi ý dựa trên vector similarity

---

### 3. Database Function `fn_recommend_top20` (PostgreSQL)

```sql
-- Chạy trong DB studynest để xem định nghĩa:
SELECT prosrc FROM pg_proc WHERE proname = 'fn_recommend_top20';
```

**Giả định logic (dựa trên tên và cách sử dụng):**
1. Lấy **user embedding** từ `user.preferences_embedding` hoặc `user_embedding_history`
2. Lấy **course embeddings** từ `courses.embedding`
3. Tính **cosine similarity** giữa user vector và course vectors
4. Lọc:
   - Chỉ khóa học `is_published = true`
   - Bỏ khóa học user đã đăng ký
5. **Sắp xếp** theo similarity giảm dần
6. **Giới hạn** 20 kết quả

---

## Request / Response

### Request

```http
GET /api/v1/courses/feed/recommend
Authorization: Bearer <access_token>
Cookie: access_token=<jwt_token>
```

### Response 200 OK

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Lập trình Python cơ bản",
      "thumbnail": "https://cdn.example.com/thumb.jpg",
      "slug": "lap-trinh-python-co-ban",
      "instructor": {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Nguyễn Văn A",
        "avatar": "https://cdn.example.com/avatar.jpg"
      },
      "similarity": 0.9234
    }
  ]
}
```

### Response 401 Unauthorized

```json
{
  "detail": "Token not found in cookies"
}
```

---

## Mobile sử dụng

### 1. Gọi API

```typescript
// mobile/src/services/course.service.ts (tạo mới hoặc mở rộng)
import { apiClient } from './apiClient';

export const getRecommendedCourses = async () => {
  const response = await apiClient.get('/courses/feed/recommend');
  return response.data.items as RecommendedCourse[];
};
```

### 2. Type definitions

```typescript
// mobile/src/types/course.ts
export interface RecommendedCourse {
  id: string;
  title: string;
  thumbnail: string | null;
  slug: string;
  instructor: {
    id: string;
    name: string;
    avatar: string | null;
  };
  similarity: number; // 0.0 - 1.0, độ tương đồng với sở thích user
}
```

### 3. Component hiển thị

```typescript
// mobile/components/features/home/RecommendedCourses.tsx
import { useState, useEffect } from 'react';
import { getRecommendedCourses } from '../../services/course.service';
import type { RecommendedCourse } from '../../types/course';

export const RecommendedCourses = () => {
  const [courses, setCourses] = useState<RecommendedCourse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRecommendedCourses()
      .then(setCourses)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton height={200} count={3} />;

  return (
    <FlatList
      horizontal
      data={courses}
      keyExtractor={item => item.id}
      renderItem={({ item }) => (
        <CourseCard
          title={item.title}
          thumbnail={item.thumbnail}
          instructorName={item.instructor.name}
          similarity={Math.round(item.similarity * 100)} // 92%
          onPress={() => router.push(`/course/${item.slug}`)}
        />
      )}
    />
  );
};
```

---

## Lưu ý

- **Chỉ hoạt động khi user đã đăng nhập** (cần token)
- **Độ tương đồng (similarity)**: giá trị từ 0.0 → 1.0. Càng gần 1.0 = khóa học càng phù hợp với sở thích user
- **User embedding** được tạo từ:
  - Khóa học đã wishlist
  - Bài học đã hoàn thành
  - Review đã viết
  - Ghi chú bài học
- Nếu user mới chưa có embedding → DB function sẽ fallback về khóa học phổ biến nhất
