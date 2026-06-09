# API: Feed — Khóa học công khai (Top-rated, Newest, Top-view)

## 3 Endpoints

| Endpoint | Mô tả | Auth |
|---|---|---|
| `GET /api/v1/courses/feed/top-rated` | Khóa học được đánh giá cao nhất | Tùy chọn |
| `GET /api/v1/courses/feed/newest` | Khóa học mới nhất | Tùy chọn |
| `GET /api/v1/courses/feed/top-view` | Khóa học có lượt xem cao nhất | Tùy chọn |

> Cả 3 endpoint **đều public** — không cần đăng nhập vẫn dùng được. Nếu có token, backend sẽ ẩn các khóa học user đã mua khỏi kết quả.

---

## Common Query Params

| Param | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `limit` | `int` | `10` | Số lượng khóa học trả về (1–50) |
| `cursor` | `string` | `null` | Con trỏ phân trang, lấy từ `next_cursor` của response trước |

---

## Response Schema chung

```json
{
  "items": [ /* mảng CourseItem, xem bên dưới */ ],
  "next_cursor": "abc123|uuid" | null
}
```

### CourseItem

```typescript
interface CourseItem {
  id: string;                    // UUID
  title: string;                 // Tiêu đề khóa học
  thumbnail: string | null;     // URL ảnh thumbnail
  slug: string;                  // Slug cho routing, dùng: /course/{slug}
  base_price: number | null;    // Giá gốc (VND)
  views: number;                 // Tổng lượt xem
  rating: number;                // Điểm TB (0–5) ← top-view & newest dùng key này
  rating_avg: number;            // Điểm TB (0–5) ← top-rated dùng key này ⚠️
  enrolls: number;               // Tổng số học viên đã đăng ký
  tags: string[];                // Tags tự động: "thịnh hành", "bán chạy nhất", "được yêu thích", "mới ra mắt"
  instructor: {
    id: string;
    name: string;                // fullname của lecturer
    avatar: string | null;
  } | null;
}
```

### ⚠️ Lưu ý key `rating` vs `rating_avg`

| Endpoint | Rating key |
|---|---|
| `top-rated` | `rating_avg` |
| `newest` | `rating` |
| `top-view` | `rating` |

---

## 1. Top-rated — Khóa học được đánh giá cao

### Luồng xử lý backend

1. Lấy **toàn bộ** stats (views, enrolls, rating) của các khóa đã duyệt
2. Tính **80th percentile** cho mỗi metric → dùng làm cutoff
3. Query: `rating_avg >= rating_cutoff` (chỉ lấy top 20% về rating)
4. Ưu tiên các khóa có views cao (lọc thêm `views >= views_cutoff`)
5. Sắp xếp: `rating_avg DESC, id DESC`
6. Gắn tags: `"thịnh hành"`, `"bán chạy nhất"`, `"được yêu thích"`, `"mới ra mắt"`

### Request mẫu

```http
GET /api/v1/courses/feed/top-rated?limit=4
GET /api/v1/courses/feed/top-rated?limit=4&cursor=4.5|550e8400-e29b-41d4-a716-446655440000
```

### Response mẫu

```json
{
  "items": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "title": "React Native thực chiến 2026",
      "thumbnail": "https://cdn.example.com/thumb1.jpg",
      "slug": "react-native-thuc-chien-2026",
      "base_price": 599000,
      "views": 15420,
      "rating_avg": 4.87,
      "enrolls": 3420,
      "tags": ["thịnh hành", "bán chạy nhất", "được yêu thích"],
      "instructor": {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "name": "Nguyễn Văn A",
        "avatar": "https://cdn.example.com/avatar1.jpg"
      }
    }
  ],
  "next_cursor": "4.87|660e8400-e29b-41d4-a716-446655440001"
}
```

---

## 2. Newest — Khóa học mới nhất

### Luồng xử lý backend

1. Lấy toàn bộ stats → tính 80th percentile cutoffs
2. Query: khóa đã approved + published
3. Ẩn khóa user đã mua (nếu có token)
4. Sắp xếp: `created_at DESC, id DESC`
5. Gắn tags (tags tự động dựa trên stats + ngày tạo)

### Request mẫu

```http
GET /api/v1/courses/feed/newest?limit=4
GET /api/v1/courses/feed/newest?limit=4&cursor=2026-05-10T12:00:00|660e8400-e29b-41d4-a716-446655440001
```

### Response mẫu

```json
{
  "items": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "FastAPI Advanced Patterns",
      "thumbnail": "https://cdn.example.com/thumb2.jpg",
      "slug": "fastapi-advanced-patterns",
      "base_price": 799000,
      "views": 2340,
      "rating": 4.55,
      "enrolls": 580,
      "tags": ["mới ra mắt"],
      "instructor": {
        "id": "990e8400-e29b-41d4-a716-446655440004",
        "name": "Trần Thị B",
        "avatar": null
      }
    }
  ],
  "next_cursor": "2026-05-08T09:30:00|880e8400-e29b-41d4-a716-446655440003"
}
```

---

## 3. Top-view — Khóa học thịnh hành (lượt xem cao)

### Luồng xử lý backend

1. Lấy toàn bộ stats → tính 80th percentile cutoffs
2. Query: `views >= views_cutoff` (chỉ lấy top 20% về lượt xem)
3. Ưu tiên khóa có enrolls/rating cao
4. Sắp xếp: `views DESC, id DESC`
5. Gắn tags

### Request mẫu

```http
GET /api/v1/courses/feed/top-view?limit=4
GET /api/v1/courses/feed/top-view?limit=4&cursor=25000|550e8400-e29b-41d4-a716-446655440000
```

### Response mẫu

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Python for Data Science",
      "thumbnail": "https://cdn.example.com/thumb3.jpg",
      "slug": "python-for-data-science",
      "base_price": 499000,
      "views": 45320,
      "rating": 4.72,
      "enrolls": 8920,
      "tags": ["thịnh hành", "bán chạy nhất", "được yêu thích"],
      "instructor": {
        "id": "110e8400-e29b-41d4-a716-446655440005",
        "name": "Lê Minh C",
        "avatar": "https://cdn.example.com/avatar3.jpg"
      }
    }
  ],
  "next_cursor": "45320|550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Mobile — Hướng dẫn tích hợp

### 1. Thêm types

```typescript
// mobile/src/types/course.ts

/** Shared feed item (top-view, newest) */
export interface FeedCourse {
  id: string
  title: string
  thumbnail: string | null
  slug: string
  base_price: number | null
  views: number
  rating: number
  enrolls: number
  tags: string[]
  instructor: {
    id: string
    name: string
    avatar: string | null
  } | null
}

/** top-rated item — dùng key `rating_avg` thay vì `rating` */
export interface TopRatedCourse extends Omit<FeedCourse, 'rating'> {
  rating_avg: number
}
```

### 2. Thêm service methods

```typescript
// mobile/src/services/course.service.ts

interface FeedParams {
  limit?: number
  nextCursor?: string | null
}

/** Lấy khóa học top-rated (đánh giá cao nhất) */
export async function getTopRatedCourses(params: FeedParams = {}) {
  const { data } = await apiClient.get<{ items: TopRatedCourse[]; next_cursor: string | null }>(
    '/courses/feed/top-rated',
    { params }
  )
  return data
}

/** Lấy khóa học mới nhất */
export async function getNewestCourses(params: FeedParams = {}) {
  const { data } = await apiClient.get<{ items: FeedCourse[]; next_cursor: string | null }>(
    '/courses/feed/newest',
    { params }
  )
  return data
}

/** Lấy khóa học thịnh hành (lượt xem cao) */
export async function getTopViewCourses(params: FeedParams = {}) {
  const { data } = await apiClient.get<{ items: FeedCourse[]; next_cursor: string | null }>(
    '/courses/feed/top-view',
    { params }
  )
  return data
}
```

### 3. Sử dụng trong HomeScreen — Thay `HomeCourseList` hard-coded

```typescript
// mobile/components/features/home/HomeCourseList.tsx

import React from 'react'
import { View, Pressable, Animated, ScrollView } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { Text } from '@/components/ui'
import { Feather } from '@expo/vector-icons'
import * as Haptics from 'expo-haptics'
import { cn } from '@/src/lib/utils'
import { getNewestCourses } from '@/src/services/course.service'
import type { FeedCourse } from '@/src/types/course'
import { getFullImageUrl } from '@/src/utils/image'

export function HomeCourseList() {
  const { data, isLoading } = useQuery({
    queryKey: ['courses', 'newest'],
    queryFn: () => getNewestCourses({ limit: 4 }),
    staleTime: 1000 * 60 * 5,
  })

  const courses = data?.items ?? []

  return (
    <View className="px-5">
      {/* Header */}
      <View className="flex-row justify-between items-end mb-5 px-1">
        <Text className="text-2xl font-extrabold tracking-tighter text-zinc-900 dark:text-zinc-50">
          Khóa học mới
        </Text>
        <Pressable>
          <Text className="text-emerald-500 font-bold text-sm">Xem tất cả</Text>
        </Pressable>
      </View>

      {/* Course list */}
      {isLoading ? (
        <CourseSkeleton count={3} />
      ) : courses.length === 0 ? (
        <EmptyCourses />
      ) : (
        <View className="gap-4">
          {courses.map(course => (
            <CourseCard key={course.id} course={course} />
          ))}
        </View>
      )}
    </View>
  )
}

function CourseCard({ course }: { course: FeedCourse }) {
  const scaleAnim = useRef(new Animated.Value(1)).current

  const handlePressIn = () => {
    Animated.spring(scaleAnim, { toValue: 0.96, useNativeDriver: true }).start()
  }
  const handlePressOut = () => {
    Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true }).start()
  }
  const handlePress = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)
  }

  const displayRating = (course as any).rating_avg ?? (course as any).rating ?? 0

  return (
    <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
      <Pressable
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        onPress={handlePress}
        className={cn(
          "p-6 rounded-[40px] flex-row items-center gap-5 border",
          "bg-white dark:bg-zinc-900/60 shadow-lg shadow-black/5",
          "border-zinc-100 dark:border-zinc-800"
        )}
      >
        {/* Thumbnail */}
        <View className="w-16 h-16 rounded-[24px] overflow-hidden bg-emerald-500/10 items-center justify-center">
          {course.thumbnail ? (
            <Image
              source={{ uri: getFullImageUrl(course.thumbnail) as string }}
              className="w-full h-full"
              resizeMode="cover"
            />
          ) : (
            <Feather name="play-circle" size={32} color="#10b981" />
          )}
        </View>

        {/* Info */}
        <View className="flex-1">
          {/* Tags */}
          {course.tags.length > 0 && (
            <View className="flex-row flex-wrap gap-1.5 mb-1.5">
              {course.tags.slice(0, 2).map(tag => (
                <View
                  key={tag}
                  className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20"
                >
                  <Text className="text-[9px] font-black text-emerald-600 dark:text-emerald-400 uppercase tracking-widest">
                    {tag}
                  </Text>
                </View>
              ))}
            </View>
          )}

          <Text
            className="text-xl font-extrabold text-zinc-900 dark:text-zinc-50 tracking-tighter leading-tight mb-1"
            numberOfLines={1}
          >
            {course.title}
          </Text>

          {/* Rating + Enrolls */}
          <View className="flex-row items-center gap-2">
            <Feather name="star" size={12} color="#f59e0b" />
            <Text className="text-xs font-bold text-amber-500">
              {displayRating.toFixed(1)}
            </Text>
            <Text className="text-xs font-bold text-zinc-400 dark:text-zinc-500">
              • {course.enrolls.toLocaleString('vi-VN')} học viên
            </Text>
          </View>
        </View>

        <Feather name="chevron-right" size={20} className="text-zinc-300 dark:text-zinc-700" />
      </Pressable>
    </Animated.View>
  )
}
```

### 4. HomeProgress — Top-view feed (mục "Đang tiếp tục")

Component `HomeProgress` hiện tại hard-coded. Thay bằng dữ liệu thực từ `top-view`:

```typescript
// mobile/components/features/home/HomeProgress.tsx

import React from 'react'
import { View, Pressable } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { Text } from '@/components/ui'
import { Feather } from '@expo/vector-icons'
import { cn } from '@/src/lib/utils'
import { getTopViewCourses } from '@/src/services/course.service'
import type { FeedCourse } from '@/src/types/course'

export function HomeProgress() {
  const { data } = useQuery({
    queryKey: ['courses', 'top-view'],
    queryFn: () => getTopViewCourses({ limit: 1 }),
    staleTime: 1000 * 60 * 10,
  })

  const topCourse = data?.items?.[0]

  if (!topCourse) return null

  return (
    <View className="px-5 mb-8">
      <View
        className={cn(
          "p-7 rounded-[40px] border shadow-2xl shadow-emerald-500/10",
          "bg-white/40 dark:bg-zinc-900/60 backdrop-blur-2xl",
          "border-white/40 dark:border-zinc-800"
        )}
      >
        <View className="flex-row items-center justify-between mb-4">
          <View className="flex-row items-center gap-3">
            <View className="w-10 h-10 rounded-full bg-emerald-500/20 items-center justify-center">
              <Feather name="book-open" size={20} className="text-emerald-500" />
            </View>
            <View>
              <Text className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-widest">
                Thịnh hành
              </Text>
              <Text
                className="text-lg font-extrabold text-zinc-900 dark:text-zinc-50 tracking-tight"
                numberOfLines={1}
              >
                {topCourse.title}
              </Text>
            </View>
          </View>
          <View className="items-end">
            <Feather name="eye" size={14} className="text-zinc-400 mb-0.5" />
            <Text className="text-2xl font-black text-emerald-500">
              {topCourse.views >= 1000
                ? `${(topCourse.views / 1000).toFixed(1)}K`
                : topCourse.views}
            </Text>
          </View>
        </View>

        <View className="h-3 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
          <View
            className="h-full bg-emerald-500 rounded-full"
            style={{ width: `${Math.min((topCourse.enrolls / 1000) * 100, 100)}%` }}
          />
        </View>

        <View className="flex-row justify-between mt-3">
          <Text className="text-xs font-medium text-zinc-500 dark:text-zinc-400" numberOfLines={1}>
            {topCourse.instructor?.name ?? 'Đang cập nhật'}
          </Text>
          <Text className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {topCourse.enrolls.toLocaleString('vi-VN')} học viên
          </Text>
        </View>
      </View>
    </View>
  )
}
```

### 5. HomeHero — Top-rated feed

Component `HomeHero` dùng ảnh static. Thay bằng khóa top-rated thực tế:

```typescript
// mobile/components/features/home/HomeHero.tsx

import React from 'react'
import { View, Image, Dimensions, Pressable } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { Text, Button } from '@/components/ui'
import { LinearGradient } from 'expo-linear-gradient'
import { useColorScheme } from 'nativewind'
import { getTopRatedCourses } from '@/src/services/course.service'
import type { TopRatedCourse } from '@/src/types/course'
import { getFullImageUrl } from '@/src/utils/image'

const { width } = Dimensions.get('window')

export function HomeHero() {
  const { colorScheme } = useColorScheme()
  const isDark = colorScheme === 'dark'

  const { data } = useQuery({
    queryKey: ['courses', 'top-rated'],
    queryFn: () => getTopRatedCourses({ limit: 1 }),
    staleTime: 1000 * 60 * 10,
  })

  const topCourse = data?.items?.[0]

  return (
    <View className="px-5 mb-8">
      <View className="relative h-[240px] rounded-[40px] overflow-hidden bg-emerald-500/10 border border-emerald-500/20">
        {/* Background image */}
        {topCourse?.thumbnail ? (
          <Image
            source={{ uri: getFullImageUrl(topCourse.thumbnail) as string }}
            className="absolute w-full h-full"
            resizeMode="cover"
          />
        ) : (
          <Image
            source={require('@/assets/images/onboarding_world.png')}
            className="absolute w-full h-full"
            resizeMode="cover"
          />
        )}

        {/* Rating badge */}
        {topCourse && (
          <View className="absolute top-3.5 right-3.5 px-3 py-1.5 rounded-full bg-black/30 backdrop-blur-sm">
            <View className="flex-row items-center gap-1.5">
              <Feather name="star" size={12} color="#f59e0b" />
              <Text className="text-sm font-black text-white">
                {(topCourse as any).rating_avg?.toFixed(1) ?? '0.0'}
              </Text>
            </View>
          </View>
        )}

        {/* Gradient overlay */}
        <LinearGradient
          colors={['transparent', isDark ? 'rgba(9,9,11,0.7)' : 'rgba(255,255,255,0.85)']}
          className="absolute inset-0"
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
        />

        {/* Content */}
        <View className="absolute bottom-8 left-8 right-8">
          {topCourse ? (
            <>
              <View className="flex-row flex-wrap gap-1.5 mb-3">
                {topCourse.tags.slice(0, 2).map(tag => (
                  <View key={tag} className="px-2.5 py-1 rounded-full bg-emerald-500/80 backdrop-blur-sm">
                    <Text className="text-[10px] font-black text-white uppercase tracking-widest">
                      {tag}
                    </Text>
                  </View>
                ))}
              </View>
              <Text className="text-3xl font-extrabold tracking-tighter text-zinc-900 dark:text-zinc-50 mb-4 leading-tight">
                {topCourse.title}
              </Text>
              <Button label="Học ngay" size="sm" className="shadow-xl shadow-emerald-500/40" />
            </>
          ) : (
            <>
              <Text className="text-3xl font-extrabold tracking-tighter text-zinc-900 dark:text-zinc-50 mb-4 leading-tight">
                Khám phá kiến thức{'\n'}cùng NeuralEarn 2026
              </Text>
              <Button label="Bắt đầu ngay" size="sm" className="shadow-xl shadow-emerald-500/40" />
            </>
          )}
        </View>
      </View>
    </View>
  )
}
```

---

## Phân trang (Cursor-based)

```typescript
// Infinite scroll hook cho feed

function useFeedCourses(type: 'newest' | 'top-rated' | 'top-view') {
  const queryFn = {
    newest: getNewestCourses,
    'top-rated': getTopRatedCourses,
    'top-view': getTopViewCourses,
  }[type]

  return useInfiniteQuery({
    queryKey: ['courses', type],
    queryFn: ({ pageParam }) => queryFn({ limit: 10, nextCursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}
```

---

## Ghi chú quan trọng

1. **`rating` vs `rating_avg`**: top-rated trả về key `rating_avg`, 2 endpoint còn lại dùng `rating` — cả 2 đều chứa cùng giá trị số
2. **Tags tự động**: backend tự gắn tags dựa trên percentile stats — không cần xử lý thêm
3. **null handling**: `thumbnail`, `instructor.avatar`, `base_price` có thể là `null`
4. **Cache**: nên set `staleTime: 5–10 phút` vì feed không thay đổi quá thường xuyên
5. **Ẩn khóa đã mua**: nếu có token, backend tự loại khóa user đã enroll khỏi kết quả
