from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ==========================================
# 1. OVERVIEW
# ==========================================
class LecturerOverviewResponse(BaseModel):
    total_revenue: float
    total_students: int
    total_courses: int
    average_rating: float
    total_reviews: int

    # Growth metrics
    this_month_revenue: float
    last_month_revenue: float
    revenue_growth: float  # Percentage

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. REVENUE CHART
# ==========================================
class RevenueChartItem(BaseModel):
    date: str  # YYYY-MM-DD or YYYY-MM depending on period
    revenue: float
    courses_sold: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. COURSE PERFORMANCE
# ==========================================
class CoursePerformanceItem(BaseModel):
    course_id: UUID
    title: str
    thumbnail: Optional[str] = None
    status: str

    revenue: float
    total_students: int
    average_rating: float
    reviews_count: int
    this_month_revenue: float

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 4. STUDENT ANALYTICS
# ==========================================
class StudentsByCourseItem(BaseModel):
    course_id: UUID
    course_title: str
    count: int


class StudentAnalyticsResponse(BaseModel):
    total_new_students: int
    active_students: int
    retention_rate: float
    students_by_course: List[StudentsByCourseItem]

    model_config = ConfigDict(from_attributes=True)
