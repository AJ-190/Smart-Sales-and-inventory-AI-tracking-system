from app import models, schemas, database
from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session
from app.utils import dependencies
from app.services import approval_service
from typing import Optional

router = APIRouter(prefix="/approvals", tags=['Approvals'])

@router.post("/send_approval", status_code=201, response_model=schemas.ApprovalsResponseUser)
def send_approval(post: schemas.ApprovalSend, 
                  db: Session = Depends(database.get_db),
                  current_user: models.Users = Depends(dependencies.get_current_user)):
    return approval_service.send_approval(post, db, current_user)

@router.get("/get_approvals/{business_id}", response_model=list[schemas.ApprovalsResponse])
def get_approvals(
                  business_id: int,
                  status: Optional[str] = None,
                  db: Session = Depends(database.get_db), 
                  current_user: models.Users = Depends(dependencies.get_current_user)):
    return approval_service.get_approvals(business_id,status, db, current_user)


@router.post("/confirm_approvals/{business_id}", response_model=schemas.ApprovalsResponse)
def confirm_approval(post: schemas.Direction,
                     business_id: int,
                     db: Session = Depends(database.get_db),
                     current_user: models.Users = Depends(dependencies.get_current_user)):
    return approval_service.con_del_approval(post, business_id,db, current_user)