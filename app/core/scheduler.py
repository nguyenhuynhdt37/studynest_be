from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.db.sesson import AsyncSessionLocal
from app.services.shares.payout import PayoutService

scheduler = AsyncIOScheduler()


async def payout_job():
    async with AsyncSessionLocal() as session:
        service = PayoutService(session)
        result = await service.payout_all_eligible()
        print("Payout batch:", result)


def start_scheduler():
    scheduler.add_job(
        payout_job,
        trigger=IntervalTrigger(minutes=1),
        id="payout_job",
        replace_existing=True,
    )
    scheduler.start()
    print("🔔 Scheduler started (payout job running every 1 minutes)")
