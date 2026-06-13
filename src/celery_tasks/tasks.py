import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.database import get_db
from src.businesses import models as bm
from src.businesses import service as biz_service

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


def summery(period: str):
    db = next(get_db())
    try:
        start, end = _get_period_range(period)
        from src.users import models as um
        users = (
            db.query(um.BusinessMember)
            .filter(um.BusinessMember.role.in_(
                [um.RoleEnum.admin,
                 um.RoleEnum.super_admin,
                 um.RoleEnum.manager]
            ))
            .all()
        )

        for user in users:
            biz_service.get_summery(user.business_id, db, user, start, end)
            print(f"[CRON] summary done for {user.user_id}")
    except Exception as e:
        logger.error(f"Error generating {period} sales summary: {e}")
    finally:
        db.close()


def daily_sale_summery():
    summery("daily")


def weekly_sale_summery():
    summery("weekly")


def monthly_sale_summery():
    summery("monthly")
