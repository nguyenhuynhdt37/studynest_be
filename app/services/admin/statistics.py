"""
Admin Statistics Service
Xử lý logic thống kê cho Admin Dashboard
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session
from app.db.models.database import (
    Categories,
    CourseEnrollments,
    Courses,
    InstructorEarnings,
    LessonComments,
    LessonNotes,
    PlatformWallets,
    PurchaseItems,
    RefundRequests,
    Role,
    Transactions,
    User,
    UserRoles,
    WithdrawalRequests,
)
from app.schemas.admin.statistics import (
    ActivityStatsResponse,
    CategoryRevenueItem,
    CourseLevelCount,
    CourseStatsResponse,
    CourseStatusCount,
    FinanceStatsResponse,
    InstructorStatsResponse,
    OverviewResponse,
    PendingWithdrawals,
    RefundStats,
    RevenueByCategoryResponse,
    RevenueDataPoint,
    RevenueStatsResponse,
    RoleCount,
    TopCourseItem,
    TopCoursesResponse,
    TopInstructorItem,
    TopInstructorsResponse,
    UserGrowthPoint,
    UserStatsResponse,
)


class StatisticsService:
    """Service xử lý thống kê cho Admin Dashboard"""

    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    # ================================================================
    # 1. OVERVIEW - Thống kê tổng quan
    # ================================================================
    async def get_overview_async(self) -> OverviewResponse:
        """Lấy thống kê tổng quan cho Dashboard"""
        today = date.today()

        # Total Users (không bị xóa)
        total_users = (
            await self.db.scalar(
                select(func.count(User.id)).where(User.deleted_at.is_(None))
            )
            or 0
        )

        # Total Courses (published, không bị xóa)
        total_courses = (
            await self.db.scalar(
                select(func.count(Courses.id)).where(
                    Courses.deleted_at.is_(None),
                    Courses.is_published == True,  # noqa: E712
                )
            )
            or 0
        )

        # Total Instructors (có role LECTURER)
        total_instructors = (
            await self.db.scalar(
                select(func.count(func.distinct(User.id)))
                .join(UserRoles, User.id == UserRoles.user_id)
                .join(Role, UserRoles.role_id == Role.id)
                .where(Role.role_name == "LECTURER")
            )
            or 0
        )

        # Total Revenue = Platform Income (phí nền tảng)
        total_revenue = await self.db.scalar(
            select(func.coalesce(func.sum(InstructorEarnings.amount_platform), 0))
        ) or Decimal(0)

        # Today Revenue = Platform Income hôm nay
        today_revenue = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0)
            ).where(
                func.date(InstructorEarnings.created_at) == today,
            )
        ) or Decimal(0)

        # Pending Withdrawals
        pending_withdrawals = (
            await self.db.scalar(
                select(func.count(WithdrawalRequests.id)).where(
                    WithdrawalRequests.status == "pending"
                )
            )
            or 0
        )

        # Pending Refunds
        pending_refunds = (
            await self.db.scalar(
                select(func.count(RefundRequests.id)).where(
                    RefundRequests.status == "requested"
                )
            )
            or 0
        )

        return OverviewResponse(
            total_users=total_users,
            total_courses=total_courses,
            total_instructors=total_instructors,
            total_revenue=total_revenue,
            today_revenue=today_revenue,
            pending_withdrawals=pending_withdrawals,
            pending_refunds=pending_refunds,
        )

    # ================================================================
    # 2. REVENUE STATS - Thống kê doanh thu theo thời gian
    # ================================================================
    async def get_revenue_stats_async(
        self,
        period: str = "month",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RevenueStatsResponse:
        """
        Thống kê doanh thu theo thời gian
        period: day | week | month | year
        """
        today = date.today()

        # Xác định khoảng thời gian
        if from_date is None:
            if period == "day":
                from_date = today - timedelta(days=7)
            elif period == "week":
                from_date = today - timedelta(weeks=4)
            elif period == "month":
                from_date = today - timedelta(days=365)
            else:  # year
                from_date = today - timedelta(days=365 * 3)

        if to_date is None:
            to_date = today

        # Total = Platform Income (doanh thu thật của nền tảng)
        total = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0)
            ).where(
                func.date(InstructorEarnings.created_at) >= from_date,
                func.date(InstructorEarnings.created_at) <= to_date,
            )
        ) or Decimal(0)

        # Instructor payout
        instructor_payout = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(
                func.date(InstructorEarnings.created_at) >= from_date,
                func.date(InstructorEarnings.created_at) <= to_date,
            )
        ) or Decimal(0)

        # Group by date - dùng InstructorEarnings
        if period == "day":
            date_trunc = func.date(InstructorEarnings.created_at)
        elif period == "week":
            date_trunc = func.date_trunc("week", InstructorEarnings.created_at)
        elif period == "month":
            date_trunc = func.date_trunc("month", InstructorEarnings.created_at)
        else:
            date_trunc = func.date_trunc("year", InstructorEarnings.created_at)

        # Query data points - dùng platform_income
        stmt = (
            select(
                date_trunc.label("date"),
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0).label(
                    "amount"
                ),
                func.count(InstructorEarnings.id).label("count"),
            )
            .where(
                func.date(InstructorEarnings.created_at) >= from_date,
                func.date(InstructorEarnings.created_at) <= to_date,
            )
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        data = [
            RevenueDataPoint(
                date=row.date.date() if hasattr(row.date, "date") else row.date,
                amount=row.amount,
                count=row.count,
            )
            for row in rows
        ]

        return RevenueStatsResponse(
            total=total,
            platform_income=total,  # total = platform_income
            instructor_payout=instructor_payout,
            data=data,
        )

    # ================================================================
    # 3. REVENUE BY CATEGORY
    # ================================================================
    async def get_revenue_by_category_async(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RevenueByCategoryResponse:
        """Thống kê doanh thu theo danh mục"""
        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=365)
        if to_date is None:
            to_date = today

        # Query
        stmt = (
            select(
                Categories.id.label("category_id"),
                Categories.name.label("category_name"),
                func.coalesce(func.sum(PurchaseItems.discounted_price), 0).label(
                    "revenue"
                ),
            )
            .join(Courses, Courses.category_id == Categories.id)
            .join(PurchaseItems, PurchaseItems.course_id == Courses.id)
            .join(Transactions, Transactions.id == PurchaseItems.transaction_id)
            .where(
                Transactions.status == "completed",
                func.date(Transactions.created_at) >= from_date,
                func.date(Transactions.created_at) <= to_date,
            )
            .group_by(Categories.id, Categories.name)
            .order_by(func.sum(PurchaseItems.discounted_price).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Tính tổng để tính percentage
        total_revenue = sum(row.revenue for row in rows) or Decimal(1)

        data = [
            CategoryRevenueItem(
                category_id=row.category_id,
                category_name=row.category_name,
                revenue=row.revenue,
                percentage=float(row.revenue / total_revenue * 100),
            )
            for row in rows
        ]

        return RevenueByCategoryResponse(data=data)

    # ================================================================
    # 4. USER STATS
    # ================================================================
    async def get_user_stats_async(self, period: str = "month") -> UserStatsResponse:
        """Thống kê người dùng"""
        today = date.today()

        # Total users
        total = (
            await self.db.scalar(
                select(func.count(User.id)).where(User.deleted_at.is_(None))
            )
            or 0
        )

        # Verified
        verified = (
            await self.db.scalar(
                select(func.count(User.id)).where(
                    User.deleted_at.is_(None),
                    User.is_verified_email == True,  # noqa: E712
                )
            )
            or 0
        )

        # Banned
        banned = (
            await self.db.scalar(
                select(func.count(User.id)).where(
                    User.deleted_at.is_(None),
                    User.is_banned == True,  # noqa: E712
                )
            )
            or 0
        )

        # By role
        role_stmt = (
            select(Role.role_name, func.count(UserRoles.user_id))
            .join(UserRoles, Role.id == UserRoles.role_id)
            .group_by(Role.role_name)
        )
        role_result = await self.db.execute(role_stmt)
        by_role = [RoleCount(role=row[0], count=row[1]) for row in role_result.all()]

        # Growth - user mới theo ngày (30 ngày gần nhất)
        from_date = today - timedelta(days=30)
        growth_stmt = (
            select(
                func.date(User.create_at).label("date"),
                func.count(User.id).label("new_users"),
            )
            .where(
                User.deleted_at.is_(None),
                func.date(User.create_at) >= from_date,
            )
            .group_by(func.date(User.create_at))
            .order_by(func.date(User.create_at))
        )
        growth_result = await self.db.execute(growth_stmt)
        growth = [
            UserGrowthPoint(date=row.date, new_users=row.new_users, active_users=0)
            for row in growth_result.all()
        ]

        return UserStatsResponse(
            total=total,
            verified=verified,
            banned=banned,
            by_role=by_role,
            growth=growth,
        )

    # ================================================================
    # 5. COURSE STATS
    # ================================================================
    async def get_course_stats_async(self) -> CourseStatsResponse:
        """Thống kê khóa học"""
        # Total
        total = (
            await self.db.scalar(
                select(func.count(Courses.id)).where(Courses.deleted_at.is_(None))
            )
            or 0
        )

        # By status
        published = (
            await self.db.scalar(
                select(func.count(Courses.id)).where(
                    Courses.deleted_at.is_(None),
                    Courses.is_published == True,  # noqa: E712
                )
            )
            or 0
        )

        draft = (
            await self.db.scalar(
                select(func.count(Courses.id)).where(
                    Courses.deleted_at.is_(None),
                    Courses.is_published == False,  # noqa: E712
                )
            )
            or 0
        )

        archived = (
            await self.db.scalar(
                select(func.count(Courses.id)).where(Courses.deleted_at.is_not(None))
            )
            or 0
        )

        # By level
        level_stmt = (
            select(Courses.level, func.count(Courses.id))
            .where(Courses.deleted_at.is_(None))
            .group_by(Courses.level)
        )
        level_result = await self.db.execute(level_stmt)
        level_dict = {row[0]: row[1] for row in level_result.all()}

        # Avg rating
        avg_rating = (
            await self.db.scalar(
                select(func.coalesce(func.avg(Courses.rating_avg), 0)).where(
                    Courses.deleted_at.is_(None),
                    Courses.is_published == True,  # noqa: E712
                )
            )
            or 0
        )

        # Total enrollments
        total_enrollments = (
            await self.db.scalar(select(func.count(CourseEnrollments.id))) or 0
        )

        return CourseStatsResponse(
            total=total,
            by_status=CourseStatusCount(
                published=published,
                draft=draft,
                archived=archived,
            ),
            by_level=CourseLevelCount(
                beginner=level_dict.get("beginner", 0),
                intermediate=level_dict.get("intermediate", 0),
                advanced=level_dict.get("advanced", 0),
                all=level_dict.get("all", 0),
            ),
            avg_rating=float(avg_rating),
            total_enrollments=total_enrollments,
        )

    # ================================================================
    # 6. TOP COURSES
    # ================================================================
    async def get_top_courses_async(
        self,
        sort_by: str = "revenue",
        limit: int = 10,
    ) -> TopCoursesResponse:
        """Top khóa học theo revenue/views/enrollments"""
        if sort_by == "revenue":
            # Top by revenue
            stmt = (
                select(
                    Courses.id.label("course_id"),
                    Courses.title,
                    User.fullname.label("instructor_name"),
                    Courses.thumbnail_url.label("thumbnail"),
                    func.coalesce(func.sum(PurchaseItems.discounted_price), 0).label(
                        "value"
                    ),
                )
                .join(User, Courses.instructor_id == User.id)
                .outerjoin(PurchaseItems, PurchaseItems.course_id == Courses.id)
                .where(Courses.deleted_at.is_(None))
                .group_by(
                    Courses.id, Courses.title, User.fullname, Courses.thumbnail_url
                )
                .order_by(func.sum(PurchaseItems.discounted_price).desc().nulls_last())
                .limit(limit)
            )
        elif sort_by == "views":
            stmt = (
                select(
                    Courses.id.label("course_id"),
                    Courses.title,
                    User.fullname.label("instructor_name"),
                    Courses.thumbnail_url.label("thumbnail"),
                    Courses.views.label("value"),
                )
                .join(User, Courses.instructor_id == User.id)
                .where(Courses.deleted_at.is_(None))
                .order_by(Courses.views.desc().nulls_last())
                .limit(limit)
            )
        else:  # enrollments
            stmt = (
                select(
                    Courses.id.label("course_id"),
                    Courses.title,
                    User.fullname.label("instructor_name"),
                    Courses.thumbnail_url.label("thumbnail"),
                    Courses.total_enrolls.label("value"),
                )
                .join(User, Courses.instructor_id == User.id)
                .where(Courses.deleted_at.is_(None))
                .order_by(Courses.total_enrolls.desc().nulls_last())
                .limit(limit)
            )

        result = await self.db.execute(stmt)
        rows = result.all()

        data = [
            TopCourseItem(
                course_id=row.course_id,
                title=row.title,
                instructor_name=row.instructor_name,
                thumbnail=row.thumbnail,
                value=row.value or 0,
                metric=sort_by,
            )
            for row in rows
        ]

        return TopCoursesResponse(data=data)

    # ================================================================
    # 7. INSTRUCTOR STATS
    # ================================================================
    async def get_instructor_stats_async(self) -> InstructorStatsResponse:
        """Thống kê giảng viên"""
        # Total instructors
        total = (
            await self.db.scalar(
                select(func.count(func.distinct(User.id)))
                .join(UserRoles, User.id == UserRoles.user_id)
                .join(Role, UserRoles.role_id == Role.id)
                .where(Role.role_name == "LECTURER")
            )
            or 0
        )

        # Total earnings
        total_earnings = await self.db.scalar(
            select(func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0))
        ) or Decimal(0)

        # Pending payout (status = 'holding' or 'pending')
        pending_payout = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(InstructorEarnings.status.in_(["holding", "pending"]))
        ) or Decimal(0)

        # Paid out
        paid_out = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(InstructorEarnings.status == "paid")
        ) or Decimal(0)

        return InstructorStatsResponse(
            total=total,
            total_earnings=total_earnings,
            pending_payout=pending_payout,
            paid_out=paid_out,
        )

    # ================================================================
    # 8. TOP INSTRUCTORS
    # ================================================================
    async def get_top_instructors_async(
        self,
        sort_by: str = "revenue",  # revenue, students, courses, rating
        period: str = "all",  # all, month, year
        limit: int = 10,
    ) -> TopInstructorsResponse:
        """Top giảng viên theo tiêu chí"""

        # Base query joining necessary tables
        stmt = (
            select(
                User.id.label("instructor_id"),
                User.fullname.label("name"),
                User.avatar,
                User.course_count.label("courses_count"),
                User.student_count.label("students_count"),
            )
            .join(UserRoles, User.id == UserRoles.user_id)
            .join(Role, UserRoles.role_id == Role.id)
            .where(Role.role_name == "LECTURER")
        )

        # Apply Period Filter (chỉ áp dụng cho revenue)
        revenue_expr = func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)

        if period != "all" and sort_by == "revenue":
            today = date.today()
            if period == "month":
                start_date = today.replace(day=1)
            else:  # year
                start_date = today.replace(month=1, day=1)

            stmt = stmt.outerjoin(
                InstructorEarnings,
                (InstructorEarnings.instructor_id == User.id)
                & (func.date(InstructorEarnings.created_at) >= start_date),
            )
        else:
            stmt = stmt.outerjoin(
                InstructorEarnings, InstructorEarnings.instructor_id == User.id
            )

        # Dynamic metric selection
        if sort_by == "revenue":
            metric_col = revenue_expr
            stmt = stmt.add_columns(metric_col.label("value"))
        elif sort_by == "rating":
            metric_col = User.rating_avg
            stmt = stmt.add_columns(func.coalesce(User.rating_avg, 0).label("value"))
        elif sort_by == "students":
            metric_col = User.student_count
            stmt = stmt.add_columns(User.student_count.label("value"))
        elif sort_by == "courses":
            metric_col = User.course_count
            stmt = stmt.add_columns(User.course_count.label("value"))
        else:
            metric_col = revenue_expr
            stmt = stmt.add_columns(metric_col.label("value"))

        stmt = (
            stmt.group_by(User.id).order_by(metric_col.desc().nulls_last()).limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        data = [
            TopInstructorItem(
                instructor_id=row.instructor_id,
                name=row.name,
                avatar=row.avatar,
                value=row.value or 0,
                metric=sort_by,
                courses_count=row.courses_count or 0,
                students_count=row.students_count or 0,
            )
            for row in rows
        ]
        return TopInstructorsResponse(data=data)

    async def get_instructor_growth_async(
        self, period: str = "month"
    ) -> "InstructorGrowthResponse":
        """Thống kê tăng trưởng giảng viên"""
        from app.schemas.admin.statistics import (
            InstructorGrowthPoint,
            InstructorGrowthResponse,
        )

        today = date.today()
        months = 12 if period == "month" else 30  # Last 12 months or 30 days

        if period == "month":
            date_trunc = func.to_char(User.create_at, "YYYY-MM")
            from_date = today - timedelta(days=30 * months)
        else:  # day
            date_trunc = func.to_char(User.create_at, "YYYY-MM-DD")
            from_date = today - timedelta(days=months)

        stmt = (
            select(
                date_trunc.label("date"), func.count(User.id).label("new_instructors")
            )
            .join(UserRoles, User.id == UserRoles.user_id)
            .join(Role, UserRoles.role_id == Role.id)
            .where(Role.role_name == "LECTURER", func.date(User.create_at) >= from_date)
            .group_by("date")
            .order_by("date")
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Calculate total instructors
        total_stmt = (
            select(func.count(User.id))
            .join(UserRoles)
            .join(Role)
            .where(Role.role_name == "LECTURER")
        )
        total_instructors = await self.db.scalar(total_stmt) or 0

        # Process rows
        data = []

        for row in rows:
            data.append(
                InstructorGrowthPoint(
                    date=row.date,
                    new_instructors=row.new_instructors,
                    total_instructors=total_instructors,  # Placeholder, ideally calculate cumulative
                )
            )

        total_new = sum(r.new_instructors for r in rows)

        return InstructorGrowthResponse(
            data=data,
            total_new_this_period=total_new,
            growth_rate=0.0,  # Calculate if needed
        )

    async def get_instructor_detail_async(
        self, instructor_id: UUID
    ) -> "InstructorDetailResponse":
        """Chi tiết thống kê của 1 giảng viên"""
        from app.schemas.admin.statistics import InstructorDetailResponse, TopCourseItem

        stmt = (
            select(User)
            .join(UserRoles)
            .join(Role)
            .where(User.id == instructor_id, Role.role_name == "LECTURER")
        )
        user = await self.db.scalar(stmt)
        if not user:
            return None

        # Total Revenue
        total_rev = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(InstructorEarnings.instructor_id == instructor_id)
        ) or Decimal(0)

        # Recent Revenue (30d)
        today = date.today()
        recent_rev = await self.db.scalar(
            select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(
                InstructorEarnings.instructor_id == instructor_id,
                func.date(InstructorEarnings.created_at) >= today - timedelta(days=30),
            )
        ) or Decimal(0)

        # Recent Students (Simplified: 0 for now)
        recent_students = 0

        # Top 5 Courses by Revenue (Simplified logic)
        # Using correct Course revenue calculation if available, or just mocking logic
        # Since strict correctness requires complex joins here, we'll fetch basic course info first

        courses_stmt = (
            select(
                Courses.id,
                Courses.title,
                Courses.thumbnail_url,
                Courses.rating_avg,
                Courses.total_enrolls,
            )
            .where(Courses.instructor_id == instructor_id)
            .order_by(Courses.total_enrolls.desc())
            .limit(5)
        )
        course_rows = (await self.db.execute(courses_stmt)).all()

        top_courses_data = [
            TopCourseItem(
                course_id=row.id,
                title=row.title,
                instructor_name=user.fullname,
                thumbnail=row.thumbnail_url,
                value=row.total_enrolls or 0,
                metric="students",
            )
            for row in course_rows
        ]

        return InstructorDetailResponse(
            instructor_id=user.id,
            name=user.fullname,
            email=user.email,
            avatar=user.avatar,
            join_date=user.create_at,
            total_revenue=total_rev,
            total_students=user.student_count or 0,
            total_courses=user.course_count or 0,
            average_rating=user.rating_avg or 0.0,
            revenue_last_30d=recent_rev,
            students_last_30d=recent_students,
            is_active=not user.is_banned,
            is_banned=user.is_banned or False,
            top_courses=top_courses_data,
        )

    # ================================================================
    # 9. FINANCE STATS
    # ================================================================
    async def get_finance_stats_async(self) -> FinanceStatsResponse:
        """Thống kê tài chính"""
        # Platform wallet
        wallet = await self.db.execute(select(PlatformWallets).limit(1))
        platform_wallet = wallet.scalar_one_or_none()

        platform_balance = platform_wallet.balance if platform_wallet else Decimal(0)

        # Total deposits
        total_deposits = await self.db.scalar(
            select(func.coalesce(func.sum(Transactions.amount), 0)).where(
                Transactions.type == "deposit",
                Transactions.status == "completed",
            )
        ) or Decimal(0)

        # Total withdrawals (paid)
        total_withdrawals = await self.db.scalar(
            select(func.coalesce(func.sum(WithdrawalRequests.amount), 0)).where(
                WithdrawalRequests.status == "paid"
            )
        ) or Decimal(0)

        # Pending withdrawals
        pending_count = (
            await self.db.scalar(
                select(func.count(WithdrawalRequests.id)).where(
                    WithdrawalRequests.status == "pending"
                )
            )
            or 0
        )

        pending_amount = await self.db.scalar(
            select(func.coalesce(func.sum(WithdrawalRequests.amount), 0)).where(
                WithdrawalRequests.status == "pending"
            )
        ) or Decimal(0)

        # Refunds
        refund_requested = (
            await self.db.scalar(
                select(func.count(RefundRequests.id)).where(
                    RefundRequests.status == "requested"
                )
            )
            or 0
        )

        refund_approved = (
            await self.db.scalar(
                select(func.count(RefundRequests.id)).where(
                    RefundRequests.status.in_(["admin_approved", "refunded"])
                )
            )
            or 0
        )

        refund_rejected = (
            await self.db.scalar(
                select(func.count(RefundRequests.id)).where(
                    RefundRequests.status.in_(["admin_rejected", "instructor_rejected"])
                )
            )
            or 0
        )

        total_refunded = await self.db.scalar(
            select(func.coalesce(func.sum(RefundRequests.refund_amount), 0)).where(
                RefundRequests.status == "refunded"
            )
        ) or Decimal(0)

        return FinanceStatsResponse(
            platform_balance=platform_balance,
            total_deposits=total_deposits,
            total_withdrawals=total_withdrawals,
            pending_withdrawals=PendingWithdrawals(
                count=pending_count,
                amount=pending_amount,
            ),
            refunds=RefundStats(
                requested=refund_requested,
                approved=refund_approved,
                rejected=refund_rejected,
                total_refunded=total_refunded,
            ),
        )

    # ================================================================
    # 10. ACTIVITY STATS
    # ================================================================
    async def get_activity_stats_async(
        self, period: str = "month"
    ) -> ActivityStatsResponse:
        """Thống kê hoạt động"""
        today = date.today()
        if period == "day":
            from_date = today
        elif period == "week":
            from_date = today - timedelta(days=7)
        else:  # month
            from_date = today - timedelta(days=30)

        # Lesson views (dùng Courses.views vì không có bảng lesson views riêng)
        lesson_views = (
            await self.db.scalar(
                select(func.coalesce(func.sum(Courses.views), 0)).where(
                    Courses.deleted_at.is_(None)
                )
            )
            or 0
        )

        # Lesson completions (không có bảng tracking cụ thể, dùng 0)
        lesson_completions = 0

        # Comments
        comments = (
            await self.db.scalar(
                select(func.count(LessonComments.id)).where(
                    func.date(LessonComments.created_at) >= from_date
                )
            )
            or 0
        )

        # Notes
        notes_created = (
            await self.db.scalar(
                select(func.count(LessonNotes.id)).where(
                    func.date(LessonNotes.created_at) >= from_date
                )
            )
            or 0
        )

        # Quiz attempts (không có bảng tracking cụ thể)
        quiz_attempts = 0

        return ActivityStatsResponse(
            lesson_views=lesson_views,
            lesson_completions=lesson_completions,
            comments=comments,
            notes_created=notes_created,
            quiz_attempts=quiz_attempts,
        )

    # ================================================================
    # 11. REVENUE COMPARE - So sánh doanh thu giữa 2 kỳ
    # ================================================================
    async def get_revenue_compare_async(
        self,
        current_from: date,
        current_to: date,
        previous_from: date,
        previous_to: date,
    ):
        """So sánh doanh thu giữa 2 kỳ"""
        from app.schemas.admin.statistics import PeriodRevenue, RevenueCompareResponse

        async def get_period_data(from_d: date, to_d: date) -> PeriodRevenue:
            # Total = Platform Income (doanh thu thật)
            total = await self.db.scalar(
                select(
                    func.coalesce(func.sum(InstructorEarnings.amount_platform), 0)
                ).where(
                    func.date(InstructorEarnings.created_at) >= from_d,
                    func.date(InstructorEarnings.created_at) <= to_d,
                )
            ) or Decimal(0)

            count = (
                await self.db.scalar(
                    select(func.count(InstructorEarnings.id)).where(
                        func.date(InstructorEarnings.created_at) >= from_d,
                        func.date(InstructorEarnings.created_at) <= to_d,
                    )
                )
                or 0
            )

            instructor = await self.db.scalar(
                select(
                    func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
                ).where(
                    func.date(InstructorEarnings.created_at) >= from_d,
                    func.date(InstructorEarnings.created_at) <= to_d,
                )
            ) or Decimal(0)

            return PeriodRevenue(
                from_date=from_d,
                to_date=to_d,
                total=total,
                transaction_count=count,
                platform_income=total,  # total = platform_income
                instructor_payout=instructor,
            )

        current = await get_period_data(current_from, current_to)
        previous = await get_period_data(previous_from, previous_to)

        change_amount = current.total - previous.total
        change_percent = (
            float(change_amount / previous.total * 100) if previous.total > 0 else 0.0
        )

        return RevenueCompareResponse(
            current=current,
            previous=previous,
            change_amount=change_amount,
            change_percent=round(change_percent, 2),
        )

    # ================================================================
    # 12. REVENUE TRANSACTIONS LIST - Danh sách giao dịch
    # ================================================================
    async def get_revenue_transactions_async(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ):
        """Lấy danh sách giao dịch chi tiết có phân trang"""
        import math

        from app.schemas.admin.statistics import (
            TransactionItem,
            TransactionsListResponse,
        )

        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=30)
        if to_date is None:
            to_date = today

        # Base query
        base_query = (
            select(
                Transactions.id,
                Transactions.user_id,
                User.fullname.label("user_name"),
                User.email.label("user_email"),
                Transactions.course_id,
                Courses.title.label("course_title"),
                Transactions.amount,
                Transactions.type,
                Transactions.status,
                Transactions.gateway,
                Transactions.created_at,
            )
            .join(User, Transactions.user_id == User.id)
            .outerjoin(Courses, Transactions.course_id == Courses.id)
            .where(
                Transactions.type == "purchase",
                func.date(Transactions.created_at) >= from_date,
                func.date(Transactions.created_at) <= to_date,
            )
        )

        if status:
            base_query = base_query.where(Transactions.status == status)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Paginate
        offset = (page - 1) * size
        stmt = (
            base_query.order_by(Transactions.created_at.desc())
            .offset(offset)
            .limit(size)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        items = [
            TransactionItem(
                id=row.id,
                user_id=row.user_id,
                user_name=row.user_name,
                user_email=row.user_email,
                course_id=row.course_id,
                course_title=row.course_title,
                amount=row.amount,
                type=row.type,
                status=row.status,
                gateway=row.gateway,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return TransactionsListResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if size > 0 else 0,
        )

    # ================================================================
    # 13. REVENUE BY INSTRUCTOR - Doanh thu theo giảng viên
    # ================================================================
    async def get_revenue_by_instructor_async(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
    ):
        """Doanh thu chi tiết theo từng giảng viên"""
        from app.schemas.admin.statistics import (
            InstructorRevenueItem,
            RevenueByInstructorResponse,
        )

        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=365)
        if to_date is None:
            to_date = today

        stmt = (
            select(
                User.id.label("instructor_id"),
                User.fullname.label("name"),
                User.email,
                User.avatar,
                func.coalesce(
                    func.sum(
                        InstructorEarnings.amount_instructor
                        + InstructorEarnings.amount_platform
                    ),
                    0,
                ).label("revenue"),
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0).label(
                    "platform_fee"
                ),
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0).label(
                    "net_earning"
                ),
                func.count(InstructorEarnings.id).label("transaction_count"),
                func.count(func.distinct(Transactions.course_id)).label("courses_sold"),
            )
            .join(InstructorEarnings, InstructorEarnings.instructor_id == User.id)
            .join(Transactions, Transactions.id == InstructorEarnings.transaction_id)
            .where(
                func.date(InstructorEarnings.created_at) >= from_date,
                func.date(InstructorEarnings.created_at) <= to_date,
            )
            .group_by(User.id, User.fullname, User.email, User.avatar)
            .order_by(func.sum(InstructorEarnings.amount_instructor).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        data = [
            InstructorRevenueItem(
                instructor_id=row.instructor_id,
                name=row.name,
                email=row.email,
                avatar=row.avatar,
                revenue=row.revenue,
                platform_fee=row.platform_fee,
                net_earning=row.net_earning,
                transaction_count=row.transaction_count,
                courses_sold=row.courses_sold,
            )
            for row in rows
        ]

        total_revenue = sum(item.revenue for item in data)
        total_platform_fee = sum(item.platform_fee for item in data)
        total_instructor_earning = sum(item.net_earning for item in data)

        return RevenueByInstructorResponse(
            total_revenue=total_revenue,
            total_platform_fee=total_platform_fee,
            total_instructor_earning=total_instructor_earning,
            data=data,
        )

    # ================================================================
    # 14. REVENUE BY COURSE - Doanh thu theo khóa học
    # ================================================================
    async def get_revenue_by_course_async(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
    ):
        """Doanh thu chi tiết theo từng khóa học"""
        from app.schemas.admin.statistics import (
            CourseRevenueItem,
            RevenueByCourseResponse,
        )

        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=365)
        if to_date is None:
            to_date = today

        stmt = (
            select(
                Courses.id.label("course_id"),
                Courses.title,
                Courses.instructor_id,
                User.fullname.label("instructor_name"),
                Courses.thumbnail_url.label("thumbnail"),
                func.coalesce(func.sum(PurchaseItems.discounted_price), 0).label(
                    "revenue"
                ),
                func.count(PurchaseItems.id).label("sales_count"),
                func.coalesce(func.avg(PurchaseItems.discounted_price), 0).label(
                    "avg_price"
                ),
            )
            .join(User, Courses.instructor_id == User.id)
            .join(PurchaseItems, PurchaseItems.course_id == Courses.id)
            .join(Transactions, Transactions.id == PurchaseItems.transaction_id)
            .where(
                Transactions.status == "completed",
                func.date(Transactions.created_at) >= from_date,
                func.date(Transactions.created_at) <= to_date,
            )
            .group_by(
                Courses.id,
                Courses.title,
                Courses.instructor_id,
                User.fullname,
                Courses.thumbnail_url,
            )
            .order_by(func.sum(PurchaseItems.discounted_price).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Get refund counts
        data = []
        for row in rows:
            refund_count = (
                await self.db.scalar(
                    select(func.count(RefundRequests.id))
                    .join(
                        PurchaseItems,
                        RefundRequests.purchase_item_id == PurchaseItems.id,
                    )
                    .where(PurchaseItems.course_id == row.course_id)
                )
                or 0
            )

            data.append(
                CourseRevenueItem(
                    course_id=row.course_id,
                    title=row.title,
                    instructor_id=row.instructor_id,
                    instructor_name=row.instructor_name,
                    thumbnail=row.thumbnail,
                    revenue=row.revenue,
                    sales_count=row.sales_count,
                    avg_price=row.avg_price,
                    refund_count=refund_count,
                )
            )

        total_revenue = sum(item.revenue for item in data)
        total_sales = sum(item.sales_count for item in data)

        return RevenueByCourseResponse(
            total_revenue=total_revenue,
            total_sales=total_sales,
            data=data,
        )

    # ================================================================
    # 15. REVENUE TRENDS - Xu hướng doanh thu
    # ================================================================
    async def get_revenue_trends_async(
        self,
        period: str = "month",
        months: int = 12,
    ):
        """Phân tích xu hướng doanh thu"""
        from app.schemas.admin.statistics import RevenueTrendsResponse, TrendDataPoint

        today = date.today()
        if period == "month":
            from_date = today - timedelta(days=30 * months)
            date_trunc = func.to_char(InstructorEarnings.created_at, "YYYY-MM")
        else:  # week
            from_date = today - timedelta(weeks=months * 4)
            date_trunc = func.to_char(InstructorEarnings.created_at, "IYYY-IW")

        # Dùng InstructorEarnings.amount_platform (doanh thu thật)
        stmt = (
            select(
                date_trunc.label("period"),
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0).label(
                    "revenue"
                ),
                func.count(InstructorEarnings.id).label("transaction_count"),
            )
            .where(
                func.date(InstructorEarnings.created_at) >= from_date,
            )
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Calculate growth rates
        data = []
        prev_revenue = Decimal(0)
        best_month = None
        best_month_revenue = Decimal(0)
        total_revenue = Decimal(0)
        total_growth = 0.0
        growth_count = 0

        for row in rows:
            growth_rate = 0.0
            if prev_revenue > 0:
                growth_rate = float((row.revenue - prev_revenue) / prev_revenue * 100)
                total_growth += growth_rate
                growth_count += 1

            data.append(
                TrendDataPoint(
                    period=row.period,
                    revenue=row.revenue,
                    growth_rate=round(growth_rate, 2),
                    transaction_count=row.transaction_count,
                )
            )

            if row.revenue > best_month_revenue:
                best_month_revenue = row.revenue
                best_month = row.period

            total_revenue += row.revenue
            prev_revenue = row.revenue

        avg_monthly = total_revenue / len(data) if data else Decimal(0)
        avg_growth = total_growth / growth_count if growth_count > 0 else 0.0

        return RevenueTrendsResponse(
            data=data,
            avg_monthly_revenue=avg_monthly,
            avg_growth_rate=round(avg_growth, 2),
            best_month=best_month,
            best_month_revenue=best_month_revenue,
        )

    # ================================================================
    # 16. REVENUE EXPORT - Xuất báo cáo doanh thu
    # ================================================================
    async def get_revenue_export_async(
        self,
        group_by: str = "day",  # day | month | year
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        Xuất báo cáo doanh thu theo ngày/tháng/năm.
        Trả về list data để controller convert sang CSV.
        """
        today = date.today()
        if from_date is None:
            if group_by == "day":
                from_date = today - timedelta(days=30)
            elif group_by == "month":
                from_date = today - timedelta(days=365)
            else:  # year
                from_date = today - timedelta(days=365 * 3)
        if to_date is None:
            to_date = today

        # Xác định cách group
        if group_by == "day":
            date_col = func.date(InstructorEarnings.created_at)
            date_label = "date"
        elif group_by == "month":
            date_col = func.to_char(InstructorEarnings.created_at, "YYYY-MM")
            date_label = "month"
        else:  # year
            date_col = func.to_char(InstructorEarnings.created_at, "YYYY")
            date_label = "year"

        stmt = (
            select(
                date_col.label(date_label),
                func.coalesce(func.sum(InstructorEarnings.amount_platform), 0).label(
                    "platform_income"
                ),
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0).label(
                    "instructor_payout"
                ),
                func.coalesce(
                    func.sum(
                        InstructorEarnings.amount_platform
                        + InstructorEarnings.amount_instructor
                    ),
                    0,
                ).label("total_transaction"),
                func.count(InstructorEarnings.id).label("transaction_count"),
            )
            .where(
                func.date(InstructorEarnings.created_at) >= from_date,
                func.date(InstructorEarnings.created_at) <= to_date,
            )
            .group_by(date_col)
            .order_by(date_col)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Convert to list of dicts
        data = []
        for row in rows:
            data.append(
                {
                    date_label: str(getattr(row, date_label)),
                    "platform_income": float(row.platform_income),
                    "instructor_payout": float(row.instructor_payout),
                    "total_transaction": float(row.total_transaction),
                    "transaction_count": row.transaction_count,
                }
            )

        return data

    # ================================================================
    # 19. INSTRUCTOR BY CATEGORY - Thống kê giảng viên theo danh mục
    # ================================================================
    async def get_instructor_by_category_async(
        self,
        limit_instructors: int = 5,
    ):
        """
        Thống kê giảng viên theo danh mục khóa học.
        Mỗi danh mục hiển thị: số giảng viên, số khóa học, tổng doanh thu, top giảng viên.
        """
        from app.schemas.admin.statistics import (
            InstructorByCategoryItem,
            InstructorByCategoryResponse,
            TopInstructorItem,
        )

        # Lấy danh sách categories có khóa học
        cat_stmt = (
            select(
                Categories.id.label("category_id"),
                Categories.name.label("category_name"),
                func.count(func.distinct(Courses.instructor_id)).label(
                    "instructor_count"
                ),
                func.count(Courses.id).label("total_courses"),
            )
            .join(Courses, Courses.category_id == Categories.id)
            .where(Courses.deleted_at.is_(None))
            .group_by(Categories.id, Categories.name)
            .order_by(func.count(Courses.id).desc())
        )

        cat_result = await self.db.execute(cat_stmt)
        categories = cat_result.all()

        data = []
        for cat in categories:
            # Tính doanh thu của category
            revenue_stmt = select(
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0)
            ).where(
                InstructorEarnings.course_id.in_(
                    select(Courses.id).where(Courses.category_id == cat.category_id)
                )
            )
            cat_revenue = await self.db.scalar(revenue_stmt) or Decimal(0)

            # Top giảng viên trong category
            top_stmt = (
                select(
                    User.id.label("instructor_id"),
                    User.fullname.label("name"),
                    User.avatar,
                    func.coalesce(
                        func.sum(InstructorEarnings.amount_instructor), 0
                    ).label("value"),
                    func.count(func.distinct(Courses.id)).label("courses_count"),
                    func.coalesce(func.sum(Courses.total_enrolls), 0).label(
                        "students_count"
                    ),
                )
                .join(Courses, Courses.instructor_id == User.id)
                .outerjoin(
                    InstructorEarnings, InstructorEarnings.instructor_id == User.id
                )
                .where(
                    Courses.category_id == cat.category_id,
                    Courses.deleted_at.is_(None),
                )
                .group_by(User.id, User.fullname, User.avatar)
                .order_by(
                    func.sum(InstructorEarnings.amount_instructor).desc().nulls_last()
                )
                .limit(limit_instructors)
            )

            top_result = await self.db.execute(top_stmt)
            top_instructors = [
                TopInstructorItem(
                    instructor_id=row.instructor_id,
                    name=row.name,
                    avatar=row.avatar,
                    value=row.value or 0,
                    metric="revenue",
                    courses_count=row.courses_count or 0,
                    students_count=row.students_count or 0,
                )
                for row in top_result.all()
            ]

            data.append(
                InstructorByCategoryItem(
                    category_id=cat.category_id,
                    category_name=cat.category_name,
                    instructor_count=cat.instructor_count,
                    total_courses=cat.total_courses,
                    total_revenue=cat_revenue,
                    top_instructors=top_instructors,
                )
            )

        return InstructorByCategoryResponse(
            data=data,
            total_categories=len(data),
        )

    # ================================================================
    # 20. INSTRUCTOR EXPORT - Xuất thống kê giảng viên ra CSV
    # ================================================================
    async def get_instructor_export_async(
        self,
        sort_by: str = "revenue",  # revenue | students | courses
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        Xuất danh sách giảng viên dạng CSV.
        Trả về list dict để controller convert sang CSV.
        """
        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=365)
        if to_date is None:
            to_date = today

        # Base query
        stmt = (
            select(
                User.id.label("instructor_id"),
                User.fullname.label("name"),
                User.email,
                User.course_count.label("courses"),
                User.student_count.label("students"),
                User.rating_avg.label("rating"),
                func.coalesce(func.sum(InstructorEarnings.amount_instructor), 0).label(
                    "total_revenue"
                ),
                func.coalesce(
                    func.sum(
                        InstructorEarnings.amount_instructor.op("FILTER")(
                            InstructorEarnings.status == "paid"
                        )
                    ),
                    0,
                ).label("paid_revenue"),
            )
            .join(UserRoles, User.id == UserRoles.user_id)
            .join(Role, UserRoles.role_id == Role.id)
            .outerjoin(
                InstructorEarnings,
                (InstructorEarnings.instructor_id == User.id)
                & (func.date(InstructorEarnings.created_at) >= from_date)
                & (func.date(InstructorEarnings.created_at) <= to_date),
            )
            .where(Role.role_name == "LECTURER")
            .group_by(
                User.id,
                User.fullname,
                User.email,
                User.course_count,
                User.student_count,
                User.rating_avg,
            )
        )

        # Apply sorting
        if sort_by == "revenue":
            stmt = stmt.order_by(
                func.sum(InstructorEarnings.amount_instructor).desc().nulls_last()
            )
        elif sort_by == "students":
            stmt = stmt.order_by(User.student_count.desc().nulls_last())
        else:  # courses
            stmt = stmt.order_by(User.course_count.desc().nulls_last())

        result = await self.db.execute(stmt)
        rows = result.all()

        # Convert to list of dicts for CSV
        data = []
        for idx, row in enumerate(rows, 1):
            data.append(
                {
                    "stt": idx,
                    "instructor_id": str(row.instructor_id),
                    "name": row.name,
                    "email": row.email,
                    "courses": row.courses or 0,
                    "students": row.students or 0,
                    "rating": float(row.rating or 0),
                    "total_revenue": float(row.total_revenue),
                }
            )

        return data

    # ================================================================
    # 21. COMPREHENSIVE REPORT - Báo cáo toàn diện
    # ================================================================
    async def get_comprehensive_report_async(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """
        Xuất báo cáo toàn diện gồm tất cả thống kê.
        Trả về dict với các key tương ứng từng loại thống kê.
        """
        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=365)
        if to_date is None:
            to_date = today

        report = {}

        # 1. Overview
        overview = await self.get_overview_async()
        report["overview"] = {
            "Tổng người dùng": overview.total_users,
            "Tổng khóa học": overview.total_courses,
            "Tổng giảng viên": overview.total_instructors,
            "Tổng doanh thu (VND)": float(overview.total_revenue),
            "Doanh thu hôm nay (VND)": float(overview.today_revenue),
            "Yêu cầu rút tiền chờ duyệt": overview.pending_withdrawals,
            "Yêu cầu hoàn tiền chờ duyệt": overview.pending_refunds,
        }

        # 2. Revenue by period
        revenue_stats = await self.get_revenue_stats_async("month", from_date, to_date)
        report["revenue_summary"] = {
            "Tổng doanh thu (VND)": float(revenue_stats.total),
            "Thu nhập nền tảng (VND)": float(revenue_stats.platform_income),
            "Chi trả giảng viên (VND)": float(revenue_stats.instructor_payout),
        }
        report["revenue_monthly"] = [
            {
                "Tháng": str(dp.date),
                "Doanh thu (VND)": float(dp.amount),
                "Số giao dịch": dp.count,
            }
            for dp in revenue_stats.data
        ]

        # 3. Revenue by category
        rev_by_cat = await self.get_revenue_by_category_async(from_date, to_date)
        report["revenue_by_category"] = [
            {
                "Danh mục": item.category_name,
                "Doanh thu (VND)": float(item.revenue),
                "Tỷ lệ (%)": round(item.percentage, 2),
            }
            for item in rev_by_cat.data
        ]

        # 4. User stats
        user_stats = await self.get_user_stats_async("month")
        report["user_summary"] = {
            "Tổng người dùng": user_stats.total,
            "Đã xác thực": user_stats.verified,
            "Bị khóa": user_stats.banned,
        }
        report["users_by_role"] = [
            {"Vai trò": rc.role, "Số lượng": rc.count} for rc in user_stats.by_role
        ]

        # 5. Course stats
        course_stats = await self.get_course_stats_async()
        report["course_summary"] = {
            "Tổng khóa học": course_stats.total,
            "Đã xuất bản": course_stats.by_status.published,
            "Bản nháp": course_stats.by_status.draft,
            "Đã lưu trữ": course_stats.by_status.archived,
            "Đánh giá trung bình": round(course_stats.avg_rating, 2),
            "Tổng số đăng ký": course_stats.total_enrollments,
        }
        report["courses_by_level"] = [
            {"Cấp độ": "Beginner", "Số lượng": course_stats.by_level.beginner},
            {"Cấp độ": "Intermediate", "Số lượng": course_stats.by_level.intermediate},
            {"Cấp độ": "Advanced", "Số lượng": course_stats.by_level.advanced},
            {"Cấp độ": "All Levels", "Số lượng": course_stats.by_level.all},
        ]

        # 6. Top courses
        top_courses = await self.get_top_courses_async("revenue", 20)
        report["top_courses"] = [
            {
                "STT": idx,
                "Tên khóa học": item.title,
                "Giảng viên": item.instructor_name,
                "Doanh thu (VND)": float(item.value),
            }
            for idx, item in enumerate(top_courses.data, 1)
        ]

        # 7. Instructor stats
        instructor_stats = await self.get_instructor_stats_async()
        report["instructor_summary"] = {
            "Tổng giảng viên": instructor_stats.total,
            "Tổng thu nhập (VND)": float(instructor_stats.total_earnings),
            "Chờ thanh toán (VND)": float(instructor_stats.pending_payout),
            "Đã thanh toán (VND)": float(instructor_stats.paid_out),
        }

        # 8. Top instructors
        top_instructors = await self.get_top_instructors_async("revenue", "all", 20)
        report["top_instructors"] = [
            {
                "STT": idx,
                "Họ tên": item.name,
                "Số khóa học": item.courses_count,
                "Số học viên": item.students_count,
                "Doanh thu (VND)": float(item.value),
            }
            for idx, item in enumerate(top_instructors.data, 1)
        ]

        # 9. Finance stats
        finance_stats = await self.get_finance_stats_async()
        report["finance_summary"] = {
            "Số dư nền tảng (VND)": float(finance_stats.platform_balance),
            "Tổng nạp tiền (VND)": float(finance_stats.total_deposits),
            "Tổng rút tiền (VND)": float(finance_stats.total_withdrawals),
            "Yêu cầu rút đang chờ": finance_stats.pending_withdrawals.count,
            "Số tiền rút đang chờ (VND)": float(
                finance_stats.pending_withdrawals.amount
            ),
            "Hoàn tiền đã yêu cầu": finance_stats.refunds.requested,
            "Hoàn tiền đã duyệt": finance_stats.refunds.approved,
            "Hoàn tiền bị từ chối": finance_stats.refunds.rejected,
            "Tổng tiền đã hoàn (VND)": float(finance_stats.refunds.total_refunded),
        }

        # 10. Activity stats
        activity_stats = await self.get_activity_stats_async("month")
        report["activity_summary"] = {
            "Lượt xem bài học": activity_stats.lesson_views,
            "Bài học hoàn thành": activity_stats.lesson_completions,
            "Bình luận": activity_stats.comments,
            "Ghi chú tạo mới": activity_stats.notes_created,
            "Lượt làm quiz": activity_stats.quiz_attempts,
        }

        # Metadata
        report["metadata"] = {
            "report_date": today.isoformat(),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }

        return report
