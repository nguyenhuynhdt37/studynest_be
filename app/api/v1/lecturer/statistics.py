from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import AuthorizationService
from app.schemas.lecturer.statistics import (
    CoursePerformanceItem,
    LecturerOverviewResponse,
    RevenueChartItem,
    StudentAnalyticsResponse,
)
from app.services.lecturer.statistics import LecturerStatisticsService

router = APIRouter(prefix="/lecturer/statistics", tags=["lecturer • Statistics"])


# ==========================================
# 1. OVERVIEW
# ==========================================
@router.get("/overview", response_model=LecturerOverviewResponse)
async def get_lecturer_overview(
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LecturerStatisticsService = Depends(LecturerStatisticsService),
):
    """
    Lấy các chỉ số tổng quan cho Dashboard giảng viên.
    """
    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_overview_async(lecturer)


# ==========================================
# 2. REVENUE CHART
# ==========================================
@router.get("/revenue-chart", response_model=List[RevenueChartItem])
async def get_revenue_chart(
    period: str = Query("month", description="month (30 days) or year (12 months)"),
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LecturerStatisticsService = Depends(LecturerStatisticsService),
):
    """
    Dữ liệu biểu đồ doanh thu.
    """
    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_revenue_chart_async(lecturer, period)


# ==========================================
# 3. COURSE PERFORMANCE
# ==========================================
@router.get("/courses", response_model=List[CoursePerformanceItem])
async def get_course_performance(
    limit: int = 10,
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LecturerStatisticsService = Depends(LecturerStatisticsService),
):
    """
    Hiệu suất của từng khóa học (Doanh thu, học viên, rating).
    """
    lecturer = await authorization.require_role(["LECTURER"])
    # Hiện tại sort mặc định theo revenue trong service
    return await service.get_course_performance_async(lecturer, limit)


# ==========================================
# 4. STUDENT ANALYTICS
# ==========================================
@router.get("/students", response_model=StudentAnalyticsResponse)
async def get_student_analytics(
    days: int = 30,
    authorization: AuthorizationService = Depends(AuthorizationService),
    service: LecturerStatisticsService = Depends(LecturerStatisticsService),
):
    """
    Phân tích học viên (Mới, Active...).
    """
    lecturer = await authorization.require_role(["LECTURER"])
    return await service.get_student_analytics_async(lecturer, days)
