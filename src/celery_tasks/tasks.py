import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.analytics import service as analytics_service

logger = logging.getLogger(__name__)


def _get_period_range(period: str):
    now = datetime.now(timezone.utc)

    if period == "daily":
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)

    elif period == "weekly":
        end = now - timedelta(days=now.weekday())
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(weeks=1)

    elif period == "monthly":
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (end - timedelta(days=1)).replace(day=1)
        start = end - timedelta(days=30)

    else:
        raise ValueError(f"Unknown period: {period}")

    return start, end


async def summery(period: str, db: AsyncSession | None = None):
    from src.users import models as um

    async def _run(db: AsyncSession):
        start, end = _get_period_range(period)
        result = await db.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.role.in_([
                    um.RoleEnum.admin,
                    um.RoleEnum.super_admin,
                    um.RoleEnum.manager
                ])
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                await analytics_service.get_summery(user.business_id, db, user, start, end)
                print(f"[CRON] summary done for {user.user_id}")
            except Exception as e:
                logger.error(f"Error generating summary for user {user.user_id}: {e}")

    if db is not None:
        await _run(db)
    else:
        from src.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _run(session)


def daily_sale_summery():
    asyncio.run(summery("daily"))


def weekly_sale_summery():
    asyncio.run(summery("weekly"))


def monthly_sale_summery():
    asyncio.run(summery("monthly"))
