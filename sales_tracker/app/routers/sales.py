from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sales_tracker.app.models import Business
from sales_tracker.app import schemas, models, database
from sales_tracker.app.utils import dependencies
from typing import Optional
from datetime import date as dt
from sales_tracker.app.services import sale_service 


router = APIRouter(prefix="/sales", tags=['Sales'])

@router.post("/", status_code=201, response_model=schemas.SaleResponse)
async def add_sale(post:schemas.SaleCreate,
             db: Session = Depends(database.get_db),
             current_user: Business = Depends(dependencies.get_current_user)):
    return sale_service.add_sale(post,db, current_user)

from datetime import date

@router.get("/", response_model=list[schemas.SaleResponse])
async def get_sales(
    db           : Session = Depends(database.get_db),
    current_user           = Depends(dependencies.get_current_user),
    limit        : int     = 10,
    skip         : int     = 0,
    date         : date | None = None,  # ← FastAPI auto converts "2026-04-01" string to date object
):
    return sale_service.get_sales(db, current_user, limit, skip, date)




@router.get("/{id}", response_model=schemas.SaleResponse)
async def get_sale(id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return sale_service.get_sale(id, db, current_user)



@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return sale_service.delete_sale(id, db, current_user)


