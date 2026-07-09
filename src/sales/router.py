from fastapi import APIRouter, Depends, status
from datetime import date
from src.database import get_db
from src.sales import schemas, service as sale_service
from src.auth import dependencies as auth_deps
from src.users import models as um

router = APIRouter()


@router.post("/sales/{business_id}", status_code=201, response_model=schemas.SaleResponse)
async def add_sale(business_id: int, post: schemas.SaleCreate,
             db=Depends(get_db),
             current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.cashier, um.RoleEnum.manager]))):
    return await sale_service.add_sale(business_id, post, db, current_user)


@router.get("/sales/{business_id}", response_model=list[schemas.SaleResponse])
async def get_sales(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier])),
    limit: int = 10,
    skip: int = 0,
    date: date | None = None,
):
    return await sale_service.get_sales(business_id, db, current_user, limit, skip, date)


@router.get("/sales/{business_id}/{id}", response_model=schemas.SaleResponse)
async def get_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]))):
    return await sale_service.get_sale(business_id, id, db, current_user)


@router.delete("/sales/{business_id}/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin]))):
    return await sale_service.delete_sale(business_id, id, db, current_user)
