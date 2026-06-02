from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import database, models
from app import schemas
from app.services import sale_analytics
from app.utils import dependencies
from datetime import date
 

router = APIRouter(prefix="/reports", tags=['Report'])


@router.get("/profit/{business_id}", response_model=schemas.ProfitResponse)
def get_profit(
    business_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
    date: date | None = None,
    end_date: date | None = None,
):
    return sale_analytics.view_profit(
        business_id,
        db=db,
        current_user=current_user,
        date=date,
        end_date=end_date
    )

@router.get("/analytics/summery/{business_id}")
def get_summery(
    business_id: int,
    db:Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
    date: date | None = None,
    end_date: date | None = None
):
    
    summery = sale_analytics.get_summery(business_id, db, current_user, date, end_date)
    return summery

@router.get("/analytics/low_stock", response_model=list[schemas.LowStockResponse])
def get_low_stock(
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user)
):
    return sale_analytics.check_stock(db, current_user)