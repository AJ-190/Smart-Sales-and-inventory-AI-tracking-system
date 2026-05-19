from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models
from app.models import Business
from app import schemas
from app.utils import dependencies
from typing import Optional
from datetime import date as dt
from app.services import sale_service 


router = APIRouter(prefix="/sales", tags=['Sales'])

@router.post("/{business_id}", status_code=201, response_model=schemas.SaleResponse)
async def add_sale(business_id: int, post:schemas.SaleCreate,
             db: Session = Depends(database.get_db),
             current_user: Business = Depends(dependencies.get_current_user)):
    return sale_service.add_sale(business_id, post,db, current_user)

from datetime import date

@router.get("/{business_id}", response_model=list[schemas.SaleResponse])
async def get_sales(
    business_id: int,
    db           : Session = Depends(database.get_db),
    current_user           = Depends(dependencies.get_current_user),
    limit        : int     = 10,
    skip         : int     = 0,
    date         : date | None = None,  
):
    return sale_service.get_sales(business_id, db, current_user, limit, skip, date)




@router.get("/{business_id}/{id}", response_model=schemas.SaleResponse)
async def get_sale(id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return sale_service.get_sale(id, db, current_user)



@router.delete("/{business_id}/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(business_id: int, id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return sale_service.delete_sale(business_id, id, db, current_user)


