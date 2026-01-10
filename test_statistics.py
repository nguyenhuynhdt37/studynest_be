"""
Test script for Admin Statistics APIs
Chạy: python3 test_statistics.py
"""

import asyncio
import sys

sys.path.insert(0, "/Users/huynh/hacker/projects/study_nest/studynest_be")

from app.core.deps import get_session


async def test_statistics_service():
    """Test StatisticsService với database thật"""
    from app.services.admin.statistics import StatisticsService

    # Lấy session
    async for db in get_session():
        service = StatisticsService(db)

        print("=" * 60)
        print("🧪 TESTING ADMIN STATISTICS SERVICE")
        print("=" * 60)

        # 1. Test Overview
        print("\n1️⃣ Testing get_overview_async()...")
        try:
            result = await service.get_overview_async()
            print(f"   ✅ OK: {result}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 2. Test Revenue Stats
        print("\n2️⃣ Testing get_revenue_stats_async()...")
        try:
            result = await service.get_revenue_stats_async(period="month")
            print(f"   ✅ OK: total={result.total}, platform={result.platform_income}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 3. Test Revenue by Category
        print("\n3️⃣ Testing get_revenue_by_category_async()...")
        try:
            result = await service.get_revenue_by_category_async()
            print(f"   ✅ OK: {len(result.data)} categories")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 4. Test User Stats
        print("\n4️⃣ Testing get_user_stats_async()...")
        try:
            result = await service.get_user_stats_async()
            print(f"   ✅ OK: total={result.total}, verified={result.verified}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 5. Test Course Stats
        print("\n5️⃣ Testing get_course_stats_async()...")
        try:
            result = await service.get_course_stats_async()
            print(
                f"   ✅ OK: total={result.total}, enrollments={result.total_enrollments}"
            )
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 6. Test Top Courses
        print("\n6️⃣ Testing get_top_courses_async()...")
        try:
            result = await service.get_top_courses_async(sort_by="revenue", limit=5)
            print(f"   ✅ OK: {len(result.data)} courses")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 7. Test Instructor Stats
        print("\n7️⃣ Testing get_instructor_stats_async()...")
        try:
            result = await service.get_instructor_stats_async()
            print(f"   ✅ OK: total={result.total}, earnings={result.total_earnings}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 8. Test Top Instructors
        print("\n8️⃣ Testing get_top_instructors_async()...")
        try:
            result = await service.get_top_instructors_async(sort_by="revenue", limit=5)
            print(f"   ✅ OK: {len(result.data)} instructors")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 9. Test Finance Stats
        print("\n9️⃣ Testing get_finance_stats_async()...")
        try:
            result = await service.get_finance_stats_async()
            print(f"   ✅ OK: balance={result.platform_balance}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 10. Test Activity Stats
        print("\n🔟 Testing get_activity_stats_async()...")
        try:
            result = await service.get_activity_stats_async(period="month")
            print(f"   ✅ OK: views={result.lesson_views}, comments={result.comments}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 60)

        break  # Exit generator


if __name__ == "__main__":
    asyncio.run(test_statistics_service())
