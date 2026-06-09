from fastapi import HTTPException, status, Depends, APIRouter
from fastapi_cli.cli import app
from typer.cli import app
from sqlalchemy.orm import Session
from app import models, schemas, database
from app.utils import dependencies
from app.services import customer_service

router = APIRouter(prefix="/business/customers", tags=['Customer'])

@router.post("/{business_id}", response_model=schemas.CustomerResponse)
def create_customer(
    business_id: int,
    post: schemas.CustomerCreate,
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
):
    return customer_service.create_customer(db, current_user, post, business_id)



@router.get("/{business_id}", response_model=list[schemas.CustomerResponse])
def get_customers(
    business_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.Users = Depends(dependencies.get_current_user),
    search: str | None = None,
    skip: int = 0,
    limit: int = 10
):
    return customer_service.get_customers(business_id, db, current_user, search, skip, limit)


@router.get("/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer(business_id: int, customer_id: int,
                 db: Session = Depends(database.get_db),
                 current_user: models.Users = Depends(dependencies.get_current_user)):
    return customer_service.get_customer(business_id, customer_id, db, current_user)


@router.put("/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(post:schemas.CustomerUpdate, business_id: int, customer_id: int,
                    db: Session = Depends(database.get_db),
                    current_user: models.Users = Depends(dependencies.get_current_user)):
    return customer_service.update_customer(post, business_id, customer_id, db, current_user)


@router.delete("/{business_id}/{customer_id}", status_code=204)
def delete_user(business_id: int, customer_id: int,
                db: Session = Depends(database.get_db), 
                current_user: models.Users = Depends(dependencies.get_current_user)):
    return customer_service.delete_customer(business_id, customer_id, db, current_user)