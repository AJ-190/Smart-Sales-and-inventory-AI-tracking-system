from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date as dt, date, datetime
from src.database import get_db
from src.businesses import schemas, service as biz_service
from src.auth import dependencies as auth_deps
from src.users import models as um
from src.celery_tasks import tasks as cron_tasks
from src.celery_tasks.scheduler import scheduler

router = APIRouter()


@router.post("/businesses/create", status_code=201, response_model=schemas.BusinessReposnse)
async def create_business(post: schemas.BusinessCreate, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.add_business(post, db, current_user)


@router.get("/businesses/my_businesses", response_model=list[schemas.BusinessWithMemberCount])
async def get_my_bussiness(db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.my_businesses(db, current_user)


@router.get("/businesses/", response_model=list[schemas.BusinessWithMemberCount])
async def get_businesses(db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_businesses(db, current_user)


@router.get("/businesses/{id}", response_model=schemas.BusinessWithMemberCount)
async def get_business(id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_business(id, db, current_user)


@router.put("/businesses/{id}", response_model=schemas.BusinessReposnse)
async def update_response(id: int, post: schemas.BusinessUpdate, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.update_business(id, post, db, current_user)


@router.delete("/businesses/{id}", status_code=204)
async def delete_business(id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.delete_business(id, db, current_user)


@router.get("/businesses/business_key/{business_id}", response_model=schemas.Business_key)
def get_business_key(business_id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_business_key(business_id, db, current_user)


@router.post("/products/{business_id}", response_model=schemas.ProductResponse, status_code=201)
def add_product(business_id: int, post: schemas.Productcreate, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.add_product(business_id, post, db, current_user)


@router.get("/products/{business_id}", response_model=list[schemas.ProductResponse])
def get_products(business_id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user),
                 limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return biz_service.get_Products(business_id, db, current_user, limit, skip, search)


@router.get("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
def get_product(business_id: int, id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user),
                limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return biz_service.get_product(business_id, id, db, current_user, limit, skip, search)


@router.put("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
def update_product(business_id: int, id: int, post: schemas.ProductUpdate, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.update_product(business_id, id, post, db, current_user)


@router.delete("/products/{business_id}/{id}", status_code=204)
def delete_product(business_id: int, id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.delete_product(business_id, id, db, current_user)


@router.post("/products/{business_id}/{id}/restock", response_model=schemas.ProductResponse)
def restock(business_id: int, id: int, post: schemas.Restock, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.restock(business_id, id, post, db, current_user)


@router.get("/products/{business_id}/low_stock", response_model=list[schemas.ProductResponse])
def low_stock(business_id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.low_stock(business_id, db, current_user)


@router.put("/products/{business_id}/{id}/deactivate", response_model=schemas.ProductResponse)
def deactivate(business_id: int, id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.deactivate(business_id, id, db, current_user)


@router.post("/sales/{business_id}", status_code=201, response_model=schemas.SaleResponse)
async def add_sale(business_id: int, post: schemas.SaleCreate,
                   db: Session = Depends(get_db),
                   current_user=Depends(auth_deps.get_current_user)):
    return biz_service.add_sale(business_id, post, db, current_user)


@router.get("/sales/{business_id}", response_model=list[schemas.SaleResponse])
async def get_sales(
    business_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    limit: int = 10,
    skip: int = 0,
    date: date | None = None,
):
    return biz_service.get_sales(business_id, db, current_user, limit, skip, date)


@router.get("/sales/{business_id}/{id}", response_model=schemas.SaleResponse)
async def get_sale(id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_sale(id, db, current_user)


@router.delete("/sales/{business_id}/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(business_id: int, id: int, db: Session = Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return biz_service.delete_sale(business_id, id, db, current_user)


@router.post("/approvals/send_approval", status_code=201, response_model=schemas.ApprovalsResponseUser)
def send_approval(post: schemas.ApprovalSend,
                  db: Session = Depends(get_db),
                  current_user=Depends(auth_deps.get_current_user)):
    return biz_service.send_approval(post, db, current_user)


@router.get("/approvals/get_approvals/{business_id}", response_model=list[schemas.ApprovalsResponse])
def get_approvals(
    business_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_approvals(business_id, status, db, current_user)


@router.post("/approvals/confirm_approvals/{business_id}", response_model=schemas.ApprovalsResponse)
def confirm_approval(post: schemas.Direction,
                     business_id: int,
                     db: Session = Depends(get_db),
                     current_user=Depends(auth_deps.get_current_user)):
    return biz_service.con_del_approval(post, business_id, db, current_user)


@router.post("/business/customers/{business_id}", response_model=schemas.CustomerResponse)
def create_customer(
    business_id: int,
    post: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
):
    return biz_service.create_customer(db, current_user, post, business_id)


@router.get("/business/customers/{business_id}", response_model=list[schemas.CustomerResponse])
def get_customers(
    business_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    search: str | None = None,
    skip: int = 0,
    limit: int = 10
):
    return biz_service.get_customers(business_id, db, current_user, search, skip, limit)


@router.get("/business/customers/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer(business_id: int, customer_id: int,
                 db: Session = Depends(get_db),
                 current_user=Depends(auth_deps.get_current_user)):
    return biz_service.get_customer(business_id, customer_id, db, current_user)


@router.put("/business/customers/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(post: schemas.CustomerUpdate, business_id: int, customer_id: int,
                    db: Session = Depends(get_db),
                    current_user=Depends(auth_deps.get_current_user)):
    return biz_service.update_customer(post, business_id, customer_id, db, current_user)


@router.delete("/business/customers/{business_id}/{customer_id}", status_code=204)
def delete_user(business_id: int, customer_id: int,
                db: Session = Depends(get_db),
                current_user=Depends(auth_deps.get_current_user)):
    return biz_service.delete_customer(business_id, customer_id, db, current_user)


@router.get("/reports/profit/{business_id}", response_model=schemas.ProfitResponse)
def get_profit(
    business_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    date: date | None = None,
    end_date: date | None = None,
):
    return biz_service.view_profit(business_id, db=db, current_user=current_user, date=date, end_date=end_date)


@router.get("/reports/analytics/summery/{business_id}")
def get_summery(
    business_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    date: date | None = None,
    end_date: date | None = None
):
    summery = biz_service.get_summery(business_id, db, current_user, date, end_date)
    return summery


@router.get("/reports/analytics/low_stock", response_model=list[schemas.LowStockResponse])
def get_low_stock(
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)
):
    return biz_service.check_stock(db, current_user)


@router.get("/reports/analytics/debts/{business_id}", response_model=list[schemas.DebtResponse])
def get_debts(
    business_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user)
):
    return biz_service.get_debts(business_id, db, current_user)


def permision(current_user):
    if current_user.role not in [um.RoleEnum.admin,
                                 um.RoleEnum.super_admin,
                                 um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")


@router.post("/admin/crons/daily_summery")
def run_daily(current_user=Depends(auth_deps.get_current_user)):
    permision(current_user)
    cron_tasks.daily_sale_summery()
    return {"status": "Daily sales cron triggered"}


@router.post("/admin/crons/weekly_summery")
def run_weekly(current_user=Depends(auth_deps.get_current_user)):
    permision(current_user)
    cron_tasks.weekly_sale_summery()
    return {"status": "Weekly sales cron triggered"}


@router.post("/admin/crons/monthly_summery")
def run_monthly(current_user=Depends(auth_deps.get_current_user)):
    permision(current_user)
    cron_tasks.monthly_sale_summery()
    return {"status": "Monthly sales cron triggered"}


@router.get("/admin/crons/jobs")
def list_jobs(current_user=Depends(auth_deps.get_current_user)):
    permision(current_user)
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]
