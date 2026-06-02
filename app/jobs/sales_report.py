import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app import database
from app.services import sale_analytics
from app import models
from fastapi import Depends
from app.utils import dependencies

logger = logging.getLogger(__name__)



def _get_period_range(period: str) -> tuple[datetime, datetime]:
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
        start = end - timedelta(days=30)  # 30-day range
        
        
    else:
        raise ValueError(f"Unknown period: {period}")
    
    return start, end



def summery(period: str):
    db = next(database.get_db())
    try:
        start, end = _get_period_range(period)
        users = (
            db.query(models.BusinessMember)
            .filter(models.BusinessMember.role.in_(
                [models.RoleEnum.admin,
                 models.RoleEnum.super_admin,
                 models.RoleEnum.manager]
                ))
            .all()
        )

        for user in users:
            sale_analytics.get_summery(user.business_id, db, user, start, end)
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


