from fastapi import APIRouter, Depends
from src.database import get_db
from src.customers import schemas, service as customer_service
from src.auth import dependencies as auth_deps

router = APIRouter()


@router.post("/business/customers/{business_id}", response_model=schemas.CustomerResponse)
async def create_customer(
    business_id: int,
    post: schemas.CustomerCreate,
    db = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
):
    return await customer_service.create_customer(db, current_user, post, business_id)


@router.get("/business/customers/{business_id}", response_model=list[schemas.CustomerResponse])
async def get_customers(
    business_id: int,
    db = Depends(get_db),
    current_user=Depends(auth_deps.get_current_user),
    search: str | None = None,
    skip: int = 0,
    limit: int = 10
):
    return await customer_service.get_customers(business_id, db, current_user, search, skip, limit)


@router.get("/business/customers/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
async def get_customer(business_id: int, customer_id: int,
                 db = Depends(get_db),
                 current_user=Depends(auth_deps.get_current_user)):
    return await customer_service.get_customer(business_id, customer_id, db, current_user)


@router.put("/business/customers/{business_id}/{customer_id}", response_model=schemas.CustomerResponse)
async def update_customer(post: schemas.CustomerUpdate, business_id: int, customer_id: int,
                    db = Depends(get_db),
                    current_user=Depends(auth_deps.get_current_user)):
    return await customer_service.update_customer(post, business_id, customer_id, db, current_user)


@router.delete("/business/customers/{business_id}/{customer_id}", status_code=204)
async def delete_user(business_id: int, customer_id: int,
                db = Depends(get_db),
                current_user=Depends(auth_deps.get_current_user)):
    return await customer_service.delete_customer(business_id, customer_id, db, current_user)
