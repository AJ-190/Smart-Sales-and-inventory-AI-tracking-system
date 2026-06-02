from fastapi import APIRouter, status, HTTPException, Depends
from app import database, models
from app import schemas
from sqlalchemy.orm import Session
from app.utils import dependencies
from app.services import business_service



router = APIRouter(prefix="/businesses", tags=['Businesses'])

@router.post("/create",status_code=201, response_model=schemas.BusinessReposnse)
async def create_business(post: schemas.BusinessCreate, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return business_service.add_business(post, db, current_user)

@router.get("/my_businesses", response_model=list[schemas.BusinessWithMemberCount])
async def get_my_bussiness(db: Session = Depends(database.get_db), current_user:models.Users = Depends(dependencies.get_current_user)):
    return business_service.my_businesses(db, current_user)

@router.get("/", response_model=list[schemas.BusinessWithMemberCount])
async def get_businesses(db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return business_service.get_businesses(db, current_user)

@router.get("/{id}", response_model=schemas.BusinessWithMemberCount)
async def get_business(id: int, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return business_service.get_business(id, db, current_user)

@router.put("/{id}" , response_model=schemas.BusinessReposnse)
async def update_response(id: int, post: schemas.BusinessUpdate, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
  return business_service.update_business(id,post, db, current_user)


@router.delete("/{id}", status_code=204)
async def delete_business(id: int, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user) ):
    return business_service.delete_business(id, db, current_user)

@router.get("/business_key/{business_id}", response_model=schemas.Business_key)
def get_business_key(business_id: int, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return business_service.get_business_key(business_id, db, current_user)
