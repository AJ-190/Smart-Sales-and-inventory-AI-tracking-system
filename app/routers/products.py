from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models
from app.core import config
from app.models import Business
from app.schemas import Productcreate, ProductResponse, ProductUpdate, Restock
from app import schemas
from app.utils import dependencies
from app.services import products_service
from typing import Optional
from app.core import security

router = APIRouter(prefix="/products", tags=['Products'])

@router.post("/{business_id}", response_model=ProductResponse, status_code=201)
def add_product(business_id: int, post: Productcreate, db: Session = Depends(database.get_db), current_user:Business = Depends(dependencies.get_current_user)):
   return products_service.add_product(business_id,post, db, current_user)


@router.get("/{business_id}", response_model=list[ProductResponse])
def get_products( business_id: int, db: Session = Depends(database.get_db),current_user: Business = Depends(dependencies.get_current_user),
    limit: int = 10,
    skip: int = 0,
    search: Optional[str] = ""):

    return products_service. get_Products(business_id, db, current_user, limit, skip, search)

@router.get("/{business_id}/{id}", response_model=ProductResponse)
def get_product(
                business_id: int,
                id: int,
                db: Session = Depends(database.get_db),
                current_user: Business = Depends(dependencies.get_current_user),
                limit: int = 10,
                skip: int = 0,
                search: Optional[str] = "" ):
    return products_service.get_product(business_id, id, db, current_user, limit, skip,search)


@router.put("/{business_id}/{id}", response_model=ProductResponse)
def update_product(business_id: int,id: int, post: ProductUpdate, db: Session = Depends(database.get_db), current_user: Business = Depends(dependencies.get_current_user)):
    return products_service.update_product(business_id, id, post, db, current_user)
        
@router.delete("/{business_id}/{id}", status_code=204)
def delete_product(business_id: int,id: int, db: Session = Depends(database.get_db), current_user: Business = Depends(dependencies.get_current_user)):
    return  products_service.delete_product(business_id,id, db, current_user)

@router.post("/{business_id}/{id}/restock", response_model=ProductResponse)
def restock(business_id: int, id: int, post: Restock, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return products_service.restock(business_id,id, post, db, current_user)


@router.get("/{business_id}/low_stock", response_model=ProductResponse)
def low_Stock(business_id: int , db:Session = Depends(database.get_db), current_user:models.Users = Depends(dependencies.get_current_user)):
    return low_Stock(business_id,db, current_user)

@router.put("/{business_id}/{id}/deactivate", response_model=ProductResponse)
def deactivate(business_id: int, id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return products_service.deactivate(business_id,id, db, current_user)