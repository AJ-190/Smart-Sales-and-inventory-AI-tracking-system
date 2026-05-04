from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sales_tracker.app.core import config, security
from sales_tracker.app import database, models, schemas
from sales_tracker.app.jobs.sales_report import summery
from sales_tracker.app.utils import dependencies
from datetime import date, datetime
from sales_tracker.app.services import sale_analytics, scheduler
from datetime import date
from sales_tracker.app.jobs import email_report
 

router = APIRouter(prefix="/reports", tags=['Report'])


@router.get("/profit", response_model=schemas.ProfitResponse)
def get_profit(
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
    date: date | None = None,
    end_date: date | None = None,
):
    return sale_analytics.view_profit(
        db=db,
        current_user=current_user,
        date=date,
        end_date=end_date
    )

@router.get("/analytics/summery")
def get_summery(
    db:Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
    date: date | None = None,
    end_date: date | None = None
):
    
    summery = sale_analytics.get_summery(db, current_user, date, end_date)
    return summery

@router.get("/analytics/low_stock", response_model=list[schemas.LowStockResponse])
def get_low_stock(
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user)
):
    return sale_analytics.check_stock(db, current_user)