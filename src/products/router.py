from fastapi import APIRouter, Depends
from typing import Optional
from src.database import get_db
from src.products import schemas, service as product_service
from src.auth import dependencies as auth_deps

router = APIRouter()


@router.post("/products/{business_id}", response_model=schemas.ProductResponse, status_code=201)
async def add_product(business_id: int, post: schemas.Productcreate, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.add_product(business_id, post, db, current_user)


@router.get("/products/{business_id}", response_model=list[schemas.ProductResponse])
async def get_products(business_id: int, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user),
                 limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return await product_service.get_Products(business_id, db, current_user, limit, skip, search)


@router.get("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
async def get_product(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user),
                limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return await product_service.get_product(business_id, id, db, current_user, limit, skip, search)


@router.put("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
async def update_product(business_id: int, id: int, post: schemas.ProductUpdate, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.update_product(business_id, id, post, db, current_user)


@router.delete("/products/{business_id}/{id}", status_code=204)
async def delete_product(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.delete_product(business_id, id, db, current_user)


@router.post("/products/{business_id}/{id}/restock", response_model=schemas.ProductResponse)
async def restock(business_id: int, id: int, post: schemas.Restock, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.restock(business_id, id, post, db, current_user)


@router.get("/products/{business_id}/low_stock", response_model=list[schemas.ProductResponse])
async def low_stock(business_id: int, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.low_stock(business_id, db, current_user)


@router.put("/products/{business_id}/{id}/deactivate", response_model=schemas.ProductResponse)
async def deactivate(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await product_service.deactivate(business_id, id, db, current_user)
