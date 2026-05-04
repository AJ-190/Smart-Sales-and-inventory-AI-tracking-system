from fastapi import APIRouter, status, HTTPException, Depends
from sales_tracker.app import database, models, schemas
from sales_tracker.app.core import security, config
from sqlalchemy.orm import Session
from sales_tracker.app.utils import dependencies
from sales_tracker.app.services import business_service


router = APIRouter(prefix="/businesses", tags=['Businesses'])

@router.post("/create",status_code=201, response_model=schemas.BusinessReposnse)
async def create_business(post: schemas.BusinessCreate, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return business_service.add_business(post, db, current_user)

@router.get("/", response_model=list[schemas.BusinessWithMemberCount])
async def get_businesses(db: Session = Depends(database.get_db), current_user: models.Business = Depends(dependencies.get_current_user)):
    return business_service.get_businesses(db, current_user)

@router.get("/{id}", response_model=schemas.BusinessWithMemberCount)
async def get_business(id: int, db: Session = Depends(database.get_db), current_user: models.Business = Depends(dependencies.get_current_user)):
    return business_service.get_business(id, db, current_user)

@router.put("/{id}" , response_model=schemas.BusinessReposnse)
async def update_response(id: int, post: schemas.BusinessUpdate, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
  return business_service.update_business(id,post, db, current_user)


@router.delete("/{id}")
async def delete_business(id: int, db: Session = Depends(database.get_db), current_user: models.Business = Depends(dependencies.get_current_user) ):
    return business_service.delete_business(id, db, current_user)