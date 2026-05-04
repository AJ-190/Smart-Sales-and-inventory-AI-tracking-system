
from fastapi import status, HTTPException , Depends, APIRouter
from sales_tracker.app.core import config, security
from sales_tracker.app import database, models, schemas
from sqlalchemy.orm import Session
from sales_tracker.app.services import users_service

from sales_tracker.app.utils import dependencies



router = APIRouter(prefix="/users", tags=['Authentication'])

@router.post("/sign_up", response_model= schemas.UserSignUpResponse, status_code=201)
def add_user(post: schemas.UserSignUp, db: Session = Depends(database.get_db)):
    return users_service.add_user(post, db)


@router.get("/", response_model=list[schemas.UsersOutUsers])
def get_users(db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return users_service.get_users(db, current_user)

@router.get("/members", response_model=list[schemas.UsersOutUsers])
def get_members(db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):

    return users_service.get_members(db, current_user)

@router.get("/all_users", response_model=list[schemas.UsersOutUsers])
def get_all_users(db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return users_service.get_all_users(db,current_user)

@router.get("/{id}", response_model=schemas.UsersOutUsers)
def get_user(id: int, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):

    return users_service.get_user(id, db, current_user)

@router.put("/{id}", response_model=schemas.UsersOutUsers)
def update_user(id: int, post: schemas.UserUpdate, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):

    return users_service.update_user(id, post, db,current_user)

@router.delete("/{id}")
def delete_user(id: int, db: Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):

    return users_service.delete_user(id, db,current_user)

@router.put("/{id}/activate", response_model=schemas.UserSignUpResponse)
def activate_user(id, db:Session = Depends(database.get_db), current_user: models.Users = Depends(dependencies.get_current_user)):
    return users_service.activate_user(id, db, current_user)