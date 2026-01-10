from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ============================================================
# 1. OVERVIEW
# ============================================================
class OverviewResponse(BaseModel):
    total_users: int
    total_courses: int
    total_instructors: int
    total_revenue: Decimal
    today_revenue: Decimal
    pending_withdrawals: int
    pending_refunds: int


# ============================================================
# 2. REVENUE STATISTICS
# ============================================================
class RevenueDataPoint(BaseModel):
    date: date
    amount: Decimal
    count: int


class RevenueStatsResponse(BaseModel):
    total: Decimal
    platform_income: Decimal
    instructor_payout: Decimal
    data: list[RevenueDataPoint]


# ============================================================
# 3. REVENUE BY CATEGORY
# ============================================================
class CategoryRevenueItem(BaseModel):
    category_id: UUID
    category_name: str
    revenue: Decimal
    percentage: float


class RevenueByCategoryResponse(BaseModel):
    data: list[CategoryRevenueItem]


# ============================================================
# 4. USER STATISTICS
# ============================================================
class RoleCount(BaseModel):
    role: str
    count: int


class UserGrowthPoint(BaseModel):
    date: date
    new_users: int
    active_users: int


class UserStatsResponse(BaseModel):
    total: int
    verified: int
    banned: int
    by_role: list[RoleCount]
    growth: list[UserGrowthPoint]


# ============================================================
# 5. COURSE STATISTICS
# ============================================================
class CourseStatusCount(BaseModel):
    published: int
    draft: int
    archived: int


class CourseLevelCount(BaseModel):
    beginner: int
    intermediate: int
    advanced: int
    all: int


class CourseStatsResponse(BaseModel):
    total: int
    by_status: CourseStatusCount
    by_level: CourseLevelCount
    avg_rating: float
    total_enrollments: int


# ============================================================
# 6. TOP COURSES
# ============================================================
class TopCourseItem(BaseModel):
    course_id: UUID
    title: str
    instructor_name: str
    thumbnail: Optional[str]
    value: Decimal | int
    metric: str


class TopCoursesResponse(BaseModel):
    data: list[TopCourseItem]


# ============================================================
# 7. INSTRUCTOR STATISTICS
# ============================================================
class InstructorStatsResponse(BaseModel):
    total: int
    total_earnings: Decimal
    pending_payout: Decimal
    paid_out: Decimal


# ============================================================
# 8. TOP INSTRUCTORS
# ============================================================
class TopInstructorItem(BaseModel):
    instructor_id: UUID
    name: str
    avatar: Optional[str]
    value: Decimal | int
    metric: str
    courses_count: int
    students_count: int


class TopInstructorsResponse(BaseModel):
    data: list[TopInstructorItem]


# ============================================================
# 9. FINANCE STATISTICS
# ============================================================
class PendingWithdrawals(BaseModel):
    count: int
    amount: Decimal


class RefundStats(BaseModel):
    requested: int
    approved: int
    rejected: int
    total_refunded: Decimal


class FinanceStatsResponse(BaseModel):
    platform_balance: Decimal
    total_deposits: Decimal
    total_withdrawals: Decimal
    pending_withdrawals: PendingWithdrawals
    refunds: RefundStats


# ============================================================
# 10. ACTIVITY STATISTICS
# ============================================================
class ActivityStatsResponse(BaseModel):
    lesson_views: int
    lesson_completions: int
    comments: int
    notes_created: int
    quiz_attempts: int


# ============================================================
# 11. REVENUE DETAIL - COMPARISON
# ============================================================
class PeriodRevenue(BaseModel):
    """Doanh thu của một kỳ"""

    from_date: date
    to_date: date
    total: Decimal
    transaction_count: int
    platform_income: Decimal
    instructor_payout: Decimal


class RevenueCompareResponse(BaseModel):
    """So sánh doanh thu giữa 2 kỳ"""

    current: PeriodRevenue
    previous: PeriodRevenue
    change_amount: Decimal
    change_percent: float


# ============================================================
# 12. REVENUE DETAIL - TRANSACTIONS LIST
# ============================================================
class TransactionItem(BaseModel):
    """Chi tiết một giao dịch"""

    id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    course_id: Optional[UUID] = None
    course_title: Optional[str] = None
    amount: Decimal
    type: str
    status: str
    gateway: Optional[str] = None
    created_at: datetime


class TransactionsListResponse(BaseModel):
    """Danh sách giao dịch có phân trang"""

    items: list[TransactionItem]
    total: int
    page: int
    size: int
    pages: int


# ============================================================
# 13. REVENUE BY INSTRUCTOR (Detail)
# ============================================================
class InstructorRevenueItem(BaseModel):
    """Doanh thu của một giảng viên"""

    instructor_id: UUID
    name: str
    email: str
    avatar: Optional[str] = None
    revenue: Decimal
    platform_fee: Decimal
    net_earning: Decimal
    transaction_count: int
    courses_sold: int


class RevenueByInstructorResponse(BaseModel):
    total_revenue: Decimal
    total_platform_fee: Decimal
    total_instructor_earning: Decimal
    data: list[InstructorRevenueItem]


# ============================================================
# 14. REVENUE BY COURSE (Detail)
# ============================================================
class CourseRevenueItem(BaseModel):
    """Doanh thu của một khóa học"""

    course_id: UUID
    title: str
    instructor_id: UUID
    instructor_name: str
    thumbnail: Optional[str] = None
    revenue: Decimal
    sales_count: int
    avg_price: Decimal
    refund_count: int


class RevenueByCourseResponse(BaseModel):
    total_revenue: Decimal
    total_sales: int
    data: list[CourseRevenueItem]


# ============================================================
# 15. REVENUE TRENDS
# ============================================================
class TrendDataPoint(BaseModel):
    """Điểm dữ liệu xu hướng"""

    period: str  # YYYY-MM hoặc YYYY-WW
    revenue: Decimal
    growth_rate: float  # % so với kỳ trước
    transaction_count: int


class RevenueTrendsResponse(BaseModel):
    """Xu hướng doanh thu"""

    data: list[TrendDataPoint]
    avg_monthly_revenue: Decimal
    avg_growth_rate: float
    best_month: Optional[str] = None
    best_month_revenue: Decimal = Decimal(0)


# ============================================================
# 16. INSTRUCTOR GROWTH
# ============================================================
class InstructorGrowthPoint(BaseModel):
    date: str  # YYYY-MM hoặc YYYY-MM-DD
    new_instructors: int
    total_instructors: int


class InstructorGrowthResponse(BaseModel):
    data: list[InstructorGrowthPoint]
    total_new_this_period: int
    growth_rate: float


# ============================================================
# 17. INSTRUCTOR DETAIL
# ============================================================
class InstructorDetailResponse(BaseModel):
    instructor_id: UUID
    name: str
    email: str
    avatar: Optional[str] = None
    join_date: datetime

    # Stats
    total_revenue: Decimal
    total_students: int
    total_courses: int
    average_rating: float

    # Recent performance (last 30 days)
    revenue_last_30d: Decimal
    students_last_30d: int

    # Status
    is_active: bool
    is_banned: bool = False

    # Top courses (summary)
    top_courses: list[TopCourseItem]


# ============================================================
# 18. INSTRUCTOR BY CATEGORY
# ============================================================
class InstructorByCategoryItem(BaseModel):
    """Thống kê giảng viên theo 1 danh mục"""

    category_id: UUID
    category_name: str
    instructor_count: int
    total_courses: int
    total_revenue: Decimal
    top_instructors: list[TopInstructorItem]


class InstructorByCategoryResponse(BaseModel):
    """Response thống kê giảng viên theo danh mục"""

    data: list[InstructorByCategoryItem]
    total_categories: int
