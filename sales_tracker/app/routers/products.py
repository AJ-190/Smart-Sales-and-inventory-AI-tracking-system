from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sales_tracker.app.models import Business
from sales_tracker.app import schemas, models, database
from sales_tracker.app.utils import dependencies
from sales_tracker.app.services import products_service
from typing import Optional
from sales_tracker.app.core import security, config


router = APIRouter(prefix="/products", tags=['Products'])

@router.post("/", response_model=schemas.ProductResponse, status_code=201)
def add_product(post: schemas.Productcreate, db: Session = Depends(database.get_db), current_user:Business = Depends(dependencies.get_current_user)):
   return products_service.add_product(post, db, current_user)

from typing import Optional

@router.get("/", response_model=list[schemas.ProductResponse])
def get_products( db: Session = Depends(database.get_db),current_user: Business = Depends(dependencies.get_current_user),
    limit: int = 10,
    skip: int = 0,
    search: Optional[str] = ""):

    return products_service. get_Products(db, current_user, limit, skip, search)

@router.get("/{id}", response_model=schemas.ProductResponse)
def get_product(id: int,
                db: Session = Depends(database.get_db),
                current_user: Business = Depends(dependencies.get_current_user),
                limit: int = 10,
                skip: int = 0,
                search: Optional[str] = "" ):
    return products_service.get_product(id, db, current_user)


@router.put("/{id}", response_model=schemas.ProductResponse)
def update_product(id: int, post: schemas.ProductUpdate, db: Session = Depends(database.get_db), current_user: Business = Depends(dependencies.get_current_user)):
    return products_service.update_product(id, post, db, current_user)
        
@router.delete("/{id}", status_code=204)
def delete_product(id: int, db: Session = Depends(database.get_db), current_user: Business = Depends(dependencies.get_current_user)):
    return  products_service.delete_product(id, db, current_user)

@router.post("/{id}/restock", response_model=schemas.ProductResponse)
def restock(id: int, post: int, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return products_service(id, post, db, current_user)


@router.get("/low_stock", response_model=schemas.ProductResponse)
def low_Stock(db:Session = Depends(database.get_db), current_user:models.Users = Depends(dependencies.get_current_user)):
    return low_Stock(db, current_user)

@router.put("/{id}/deactivate", response_model=schemas.ProductResponse)
def deactivate(id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return products_service.deactivate(id, db, current_user)