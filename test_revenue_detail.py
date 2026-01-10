"""
Test script for Revenue Detail APIs
Chạy: source .venv/bin/activate && python test_revenue_detail.py
"""

import asyncio
import sys
from datetime import date, timedelta

sys.path.insert(0, "/Users/huynh/hacker/projects/study_nest/studynest_be")

from app.core.deps import get_session


async def test_revenue_detail():
    """Test Revenue Detail APIs"""
    from app.services.admin.statistics import StatisticsService

    async for db in get_session():
        service = StatisticsService(db)
        today = date.today()

        print("=" * 60)
        print("🧪 TESTING REVENUE DETAIL APIS")
        print("=" * 60)

        # 11. Test Revenue Compare
        print("\n11️⃣ Testing get_revenue_compare_async()...")
        try:
            result = await service.get_revenue_compare_async(
                current_from=today - timedelta(days=30),
                current_to=today,
                previous_from=today - timedelta(days=60),
                previous_to=today - timedelta(days=31),
            )
            print(
                f"   ✅ OK: current={result.current.total}, previous={result.previous.total}, change={result.change_percent}%"
            )
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 12. Test Revenue Transactions
        print("\n12️⃣ Testing get_revenue_transactions_async()...")
        try:
            result = await service.get_revenue_transactions_async(page=1, size=5)
            print(f"   ✅ OK: {len(result.items)} items, total={result.total}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 13. Test Revenue By Instructor
        print("\n13️⃣ Testing get_revenue_by_instructor_async()...")
        try:
            result = await service.get_revenue_by_instructor_async(limit=5)
            print(
                f"   ✅ OK: {len(result.data)} instructors, total_revenue={result.total_revenue}"
            )
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 14. Test Revenue By Course
        print("\n14️⃣ Testing get_revenue_by_course_async()...")
        try:
            result = await service.get_revenue_by_course_async(limit=5)
            print(
                f"   ✅ OK: {len(result.data)} courses, total_revenue={result.total_revenue}"
            )
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # 15. Test Revenue Trends
        print("\n15️⃣ Testing get_revenue_trends_async()...")
        try:
            result = await service.get_revenue_trends_async(period="month", months=6)
            print(
                f"   ✅ OK: {len(result.data)} periods, avg_monthly={result.avg_monthly_revenue}, best={result.best_month}"
            )
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        print("\n" + "=" * 60)
        print("✅ ALL REVENUE DETAIL TESTS COMPLETED")
        print("=" * 60)

        break


if __name__ == "__main__":
    asyncio.run(test_revenue_detail())
