from fastapi import APIRouter, Depends, status
from datetime import date
from src.db.database import get_db
from src.sales import schemas, service as sale_service
from src.auth import dependencies as auth_deps
from src.users import models as um
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=['Sales'])

roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}

@router.post("/sales/{business_id}", status_code=201, response_model=schemas.SaleResponse)
async def add_sale(business_id: int, post: schemas.SaleCreate,
             db=Depends(get_db),
             current_user=Depends(auth_deps.role_checker([*roles]))):
    return await sale_service.add_sale(business_id, post, db, current_user)    

@router.get("/sales/{business_id}", response_model=list[schemas.SaleResponse])
async def get_sales(
    business_id: int,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
    limit: int = 10,
    skip: int = 0,
    date: date | None = None,
):
    return await sale_service.get_sales(business_id, db, current_user, limit, skip, date)


@router.get("/sales/{business_id}/{id}", response_model=schemas.SaleResponse)
async def get_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles]))):
    return await sale_service.get_sale(business_id, id, db, current_user)


@router.delete("/sales/{business_id}/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]))):
    return await sale_service.delete_sale(business_id, id, db, current_user)


@router.put("/sale/{business_id}/{sale_id}", response_model=schemas.SaleResponse)
async def update_sale(business_id: int, sale_id: int, 
                      sale_data:schemas.SaleCreate,
                      current_user = Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager, um.RoleEnum.cashier])),
                      session: AsyncSession = Depends(get_db)
                      ):
    return await sale_service.update_sale(business_id, sale_id, sale_data, current_user, session)


@router.get("{business_id}/{sale_id}/reciept")
async def generate_reciept(business_id: int, sale_id: int):
    return