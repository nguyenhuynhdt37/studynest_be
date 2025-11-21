from datetime import datetime

import httpx
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.db.sesson import AsyncSessionLocal
from app.services.shares.notification import NotificationService
from app.services.shares.payout import PayoutService
from app.services.shares.paypal_service import PayPalService
from app.services.shares.withdraw import WithdrawService

scheduler = AsyncIOScheduler()


# ================================
# JOB 1 — Refund payout (Hệ thống cũ)
# ================================
async def payout_job():
    logger.info("🔎 Running refund payout job...")

    async with AsyncSessionLocal() as session:
        service = PayoutService(session)
        try:
            result = await service.payout_all_eligible()
            logger.success(f"✔ Refund payout result: {result}")
        except Exception as e:
            logger.error(f"❌ Refund payout job error: {e}")


# ================================
# JOB 2 — Rút tiền: Gửi lệnh sang PayPal
# ================================
async def withdraw_process_job(http_client: httpx.AsyncClient):
    logger.info("🚀 Running withdraw: process_payout_async...")

    async with AsyncSessionLocal() as session:
        service = WithdrawService(session)
        paypal = PayPalService(http=http_client)
        notify = NotificationService(session)

        try:
            result = await service.process_payout_async(
                paypal=paypal,
                notification_service=notify,
            )
            logger.success(f"✔ Withdraw process result: {result}")
        except Exception as e:
            logger.error(f"❌ Withdraw process job error: {e}")


# ================================
# JOB 3 — Rút tiền: Kiểm tra trạng thái PayPal
# ================================
async def withdraw_check_job(http_client: httpx.AsyncClient):
    logger.info("🔍 Running withdraw: check_payout_status...")

    async with AsyncSessionLocal() as session:
        service = WithdrawService(session)
        paypal = PayPalService(http=http_client)
        notify = NotificationService(session)

        try:
            result = await service.check_payout_status(
                notification_service=notify,
                paypal=paypal,
            )
            logger.success(f"✔ Withdraw check result: {result}")
        except Exception as e:
            logger.error(f"❌ Withdraw check job error: {e}")


# ================================
# START ALL JOBS
# ================================
def start_scheduler(http_client: httpx.AsyncClient):
    now = datetime.now()

    # ------------------------------------------
    # JOB 1: Refund payout (hệ thống cũ) — mỗi 30 phút
    # ------------------------------------------
    try:
        scheduler.add_job(
            payout_job,
            trigger=IntervalTrigger(minutes=30),
            id="refund_payout_job",
            replace_existing=True,
            max_instances=1,
        )
    except ConflictingIdError:
        logger.warning("⚠ refund_payout_job existed")

    # ------------------------------------------
    # JOB 2: Withdraw → gửi PayPal
    # chạy ngay lúc khởi động
    # ------------------------------------------
    try:
        scheduler.add_job(
            withdraw_process_job,  # KHÔNG ĐƯỢC GỌI (), phải truyền function
            trigger=IntervalTrigger(minutes=1),
            next_run_time=now,
            id="withdraw_process_job",
            kwargs={"http_client": http_client},
            replace_existing=True,
            max_instances=1,
        )
    except ConflictingIdError:
        logger.warning("⚠ withdraw_process_job existed")

    # ------------------------------------------
    # JOB 3: Withdraw → check trạng thái PayPal
    # chạy sau JOB 2 đúng 30 phút
    # ------------------------------------------
    try:
        scheduler.add_job(
            withdraw_check_job,
            trigger=IntervalTrigger(minutes=1),
            # next_run_time=now + timedelta(minutes=1),
            id="withdraw_check_job",
            kwargs={"http_client": http_client},
            replace_existing=True,
            max_instances=1,
        )
    except ConflictingIdError:
        logger.warning("⚠ withdraw_check_job existed")

    scheduler.start()
    logger.info("🔔 ALL scheduler started (refund + withdraw process + withdraw check)")
