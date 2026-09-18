from fastapi import APIRouter, Depends, HTTPException, status
from datetime import date as date_type
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from src.db.database import get_db
from src.sales import schemas, service as sale_service
from src.businesses import models as bm
from src.auth import dependencies as auth_deps
from src.users import models as um
from src.auth.roles import ALL_ROLES
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=['Sales'])

roles = ALL_ROLES

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
    date: date_type | None = None,
):
    return await sale_service.get_sales(business_id, db, current_user, limit, skip, date)


@router.get("/sales/{business_id}/{id}", response_model=schemas.SaleResponse)
async def get_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles]))):
    return await sale_service.get_sale(business_id, id, db, current_user)


@router.delete("/sales/{business_id}/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]))):
    return await sale_service.delete_sale(business_id, id, db, current_user)


@router.put("/sales/{business_id}/{sale_id}", response_model=schemas.SaleResponse)
async def update_sale(business_id: int, sale_id: int, 
                      sale_data: schemas.SaleUpdate,
                      current_user = Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager, um.RoleEnum.cashier])),
                      session: AsyncSession = Depends(get_db)
                      ):
    return await sale_service.update_sale(business_id, sale_id, sale_data, current_user, session)


@router.get("/sales/{business_id}/{sale_id}/receipt")
async def generate_receipt(
    business_id: int,
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(auth_deps.role_checker([*roles])),
):
    result = await db.execute(
        select(bm.Sale)
        .options(
            joinedload(bm.Sale.sales_items).joinedload(bm.SalesItem.product),
            joinedload(bm.Sale.business),
            joinedload(bm.Sale.customer))
        .where(bm.Sale.business_id == business_id)
        .where(bm.Sale.sale_id == sale_id)
    )
    sale = result.unique().scalars().first()

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {sale_id} not found")

    business = sale.business
    return {
        "sale_id": sale.sale_id,
        "business": {
            "name": business.name if business else None,
            "phone": None,
        },
        "customer": {
            "name": sale.customer.name if sale.customer else "Walk-in Customer",
            "phone": sale.customer.phone if sale.customer else None,
        },
        "items": [
            {
                "product_id": item.product_id,
                "name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "subtotal": float(item.subtotal),
            }
            for item in sale.sales_items
        ],
        "total": float(sale.total_amount),
        "amount_paid": float(sale.amount_paid),
        "payment_method": sale.payment_method,
        "created_at": sale.created_at.isoformat() if sale.created_at else None,
    }