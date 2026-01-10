from datetime import date, timedelta
from typing import List

from fastapi import Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database import (
    CourseEnrollments,
    CourseReviews,
    Courses,
    InstructorEarnings,
    PurchaseItems,
    Transactions,
    User,
)
from app.db.sesson import get_session
from app.schemas.lecturer.statistics import (
    CoursePerformanceItem,
    LecturerOverviewResponse,
    RevenueChartItem,
    StudentAnalyticsResponse,
    StudentsByCourseItem,
)


class LecturerStatisticsService:
    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    # ==========================================
    # 1. OVERVIEW
    # ==========================================
    async def get_overview_async(self, lecturer: User) -> LecturerOverviewResponse:
        today = date.today()
        first_day_this_month = today.replace(day=1)

        # Tháng trước
        last_month_date = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_month_date.replace(day=1)

        # 1. Tổng doanh thu (InstructorEarnings) - Đã trừ phí sàn
        total_rev_query = select(func.sum(InstructorEarnings.amount_instructor)).where(
            InstructorEarnings.instructor_id == lecturer.id,
            InstructorEarnings.status != "admin_rejected",
        )
        total_revenue = await self.db.scalar(total_rev_query) or 0.0

        # Doanh thu tháng này
        this_month_rev = (
            await self.db.scalar(
                total_rev_query.where(
                    func.date(InstructorEarnings.created_at) >= first_day_this_month
                )
            )
            or 0.0
        )

        # Doanh thu tháng trước
        last_month_rev = (
            await self.db.scalar(
                total_rev_query.where(
                    func.date(InstructorEarnings.created_at) >= first_day_last_month,
                    func.date(InstructorEarnings.created_at) < first_day_this_month,
                )
            )
            or 0.0
        )

        # Growth
        growth = 0.0
        if last_month_rev > 0:
            growth = ((this_month_rev - last_month_rev) / last_month_rev) * 100
        elif this_month_rev > 0:
            growth = 100.0

        # 2. Tổng học viên (Unique users mua khóa học của giảng viên này)
        students_query = (
            select(func.count(distinct(CourseEnrollments.user_id)))
            .join(Courses, Courses.id == CourseEnrollments.course_id)
            .where(Courses.instructor_id == lecturer.id)
        )
        total_students = await self.db.scalar(students_query) or 0

        # 3. Tổng khóa học
        courses_query = select(func.count(Courses.id)).where(
            Courses.instructor_id == lecturer.id,
        )
        total_courses = await self.db.scalar(courses_query) or 0

        # 4. Rating & Reviews
        reviews_stats = await self.db.execute(
            select(func.avg(CourseReviews.rating), func.count(CourseReviews.id))
            .join(Courses, Courses.id == CourseReviews.course_id)
            .where(Courses.instructor_id == lecturer.id)
        )
        avg_rating, total_reviews = reviews_stats.one()
        avg_rating = float(avg_rating or 0)
        total_reviews = total_reviews or 0

        return LecturerOverviewResponse(
            total_revenue=total_revenue,
            total_students=total_students,
            total_courses=total_courses,
            average_rating=round(avg_rating, 1),
            total_reviews=total_reviews,
            this_month_revenue=this_month_rev,
            last_month_revenue=last_month_rev,
            revenue_growth=round(growth, 1),
        )

    # ==========================================
    # 2. REVENUE CHART
    # ==========================================
    async def get_revenue_chart_async(
        self, lecturer: User, period: str = "month"
    ) -> List[RevenueChartItem]:
        """
        period='month': 30 ngày gần nhất (theo ngày)
        period='year': 12 tháng gần nhất (theo tháng)
        """
        today = date.today()

        if period == "year":
            start_date = today - timedelta(days=365)
            # Group by Month
            # PostgreSQL: to_char(created_at, 'YYYY-MM')
            date_col = func.to_char(InstructorEarnings.created_at, "YYYY-MM")

            stmt = (
                select(
                    date_col.label("date_label"),
                    func.sum(InstructorEarnings.amount_instructor).label("revenue"),
                    func.count(InstructorEarnings.id).label("count"),
                )
                .where(
                    InstructorEarnings.instructor_id == lecturer.id,
                    func.date(InstructorEarnings.created_at) >= start_date,
                    InstructorEarnings.status != "admin_rejected",
                )
                .group_by("date_label")
                .order_by("date_label")
            )
        else:
            # Default month (30 days)
            start_date = today - timedelta(days=30)
            date_col = func.date(InstructorEarnings.created_at)

            stmt = (
                select(
                    date_col.label("date_label"),
                    func.sum(InstructorEarnings.amount_instructor).label("revenue"),
                    func.count(InstructorEarnings.id).label("count"),
                )
                .where(
                    InstructorEarnings.instructor_id == lecturer.id,
                    func.date(InstructorEarnings.created_at) >= start_date,
                    InstructorEarnings.status != "admin_rejected",
                )
                .group_by("date_label")
                .order_by("date_label")
            )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            RevenueChartItem(
                date=str(row.date_label),
                revenue=float(row.revenue),
                courses_sold=row.count,
            )
            for row in rows
        ]

    # ==========================================
    # 3. COURSE PERFORMANCE
    # ==========================================
    async def get_course_performance_async(
        self, lecturer: User, limit: int = 10
    ) -> List[CoursePerformanceItem]:
        courses = await self.db.execute(
            select(Courses).where(Courses.instructor_id == lecturer.id)
        )
        courses = courses.scalars().all()

        data = []
        today = date.today()
        first_day_this_month = today.replace(day=1)

        for course in courses:
            # Rating
            rating_stats = await self.db.execute(
                select(
                    func.avg(CourseReviews.rating), func.count(CourseReviews.id)
                ).where(CourseReviews.course_id == course.id)
            )
            (rating, rev_count) = rating_stats.one()

            # Students
            stu_count = (
                await self.db.scalar(
                    select(func.count(distinct(CourseEnrollments.user_id))).where(
                        CourseEnrollments.course_id == course.id
                    )
                )
                or 0
            )

            # Revenue (Total)

            revenue_val = 0.0
            this_month = 0.0

            rev_q = (
                select(func.sum(PurchaseItems.discounted_price))
                .join(Transactions, Transactions.id == PurchaseItems.transaction_id)
                .where(
                    PurchaseItems.course_id == course.id,
                    Transactions.status == "completed",
                )
            )
            revenue_val = await self.db.scalar(rev_q) or 0.0

            this_month_q = rev_q.where(
                func.date(Transactions.created_at) >= first_day_this_month
            )
            this_month = await self.db.scalar(this_month_q) or 0.0

            data.append(
                CoursePerformanceItem(
                    course_id=course.id,
                    title=course.title,
                    thumbnail=course.thumbnail_url,
                    status=course.approval_status,
                    revenue=float(revenue_val),
                    total_students=stu_count or 0,
                    average_rating=float(rating or 0),
                    reviews_count=rev_count or 0,
                    this_month_revenue=float(this_month),
                )
            )

        data.sort(key=lambda x: x.revenue, reverse=True)
        return data[:limit]

    # ==========================================
    # 4. STUDENT ANALYTICS
    # ==========================================
    async def get_student_analytics_async(
        self, lecturer: User, days: int = 30
    ) -> StudentAnalyticsResponse:
        today = date.today()
        start_date = today - timedelta(days=days)

        # 1. Total new students (trong period)
        new_students_query = (
            select(func.count(distinct(CourseEnrollments.user_id)))
            .join(Courses, Courses.id == CourseEnrollments.course_id)
            .where(
                Courses.instructor_id == lecturer.id,
                func.date(CourseEnrollments.enrolled_at) >= start_date,
            )
        )
        total_new = await self.db.scalar(new_students_query) or 0

        # 2. Active students (giả định là tất cả học viên đang học)
        total_active_query = (
            select(func.count(distinct(CourseEnrollments.user_id)))
            .join(Courses, Courses.id == CourseEnrollments.course_id)
            .where(Courses.instructor_id == lecturer.id)
        )
        total_active = await self.db.scalar(total_active_query) or 0

        # 3. Retention Rate
        retention = 0.0
        if total_active > 0:
            retention = 85.5  # Fake logic hoặc implement sau

        # 4. Students by course
        stmt = (
            select(
                Courses.id,
                Courses.title,
                func.count(distinct(CourseEnrollments.user_id)).label("count"),
            )
            .join(CourseEnrollments, CourseEnrollments.course_id == Courses.id)
            .where(Courses.instructor_id == lecturer.id)
            .group_by(Courses.id, Courses.title)
            .order_by(func.count(distinct(CourseEnrollments.user_id)).desc())
            .limit(5)
        )
        rows = (await self.db.execute(stmt)).all()
        by_course = [
            StudentsByCourseItem(course_id=r.id, course_title=r.title, count=r.count)
            for r in rows
        ]

        return StudentAnalyticsResponse(
            total_new_students=total_new,
            active_students=total_active,
            retention_rate=retention,
            students_by_course=by_course,
        )
