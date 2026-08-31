from fastapi import APIRouter, Depends, File, UploadFile
from typing import Optional
from src.db.database import get_db
from src.products import schemas, service as product_service
from src.auth import dependencies as auth_deps
from src.users import models as um
from src.businesses import models as bm
router = APIRouter(tags=['Product'])

roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}


@router.post("/products/{business_id}", response_model=schemas.ProductResponse, status_code=201)
async def add_product(business_id: int, post: schemas.Productcreate, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles]))):
    return await product_service.add_product(business_id, post, db, current_user)


@router.post("/upload/products", status_code=201)
async def upload_file(business_id: int, file: UploadFile = File(...), current_user = Depends(auth_deps.role_checker([*roles])), session = Depends(get_db)):
    return await product_service.upload_file(file, current_user,session, business_id)

@router.get("/download/products", status_code=200)
async def export_products(business_id, 
                          file_format,
                          current_user = Depends(auth_deps.role_checker([*roles])),
                          session = Depends(get_db)):
    return await product_service.export_products(current_user,session, business_id, file_format)
@router.get("/products/{business_id}", response_model=list[schemas.ProductResponse])
async def get_products(business_id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles])),
                 limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return await product_service.get_Products(business_id, db, current_user, limit, skip, search)


@router.get("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
async def get_product(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles])),
                limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    return await product_service.get_product(business_id, id, db, current_user, limit, skip, search)


@router.put("/products/{business_id}/{id}", response_model=schemas.ProductResponse)
async def update_product(business_id: int, id: int, post: schemas.ProductUpdate, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    return await product_service.update_product(business_id, id, post, db, current_user)


@router.delete("/products/{business_id}/{id}", status_code=204)
async def delete_product(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin]))):
    return await product_service.delete_product(business_id, id, db, current_user)


@router.post("/products/{business_id}/{id}/restock", response_model=schemas.ProductResponse)
async def restock(business_id: int, id: int, post: schemas.Restock, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]))):
    return await product_service.restock(business_id, id, post, db, current_user)


@router.get("/products/{business_id}/low_stock", response_model=list[schemas.ProductResponse])
async def low_stock(business_id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles]))):
    return await product_service.low_stock(business_id, db, current_user)


@router.put("/products/{business_id}/{id}/deactivate", response_model=schemas.ProductResponse)
async def deactivate(business_id: int, id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.admin, um.RoleEnum.super_admin]))):
    return await product_service.deactivate(business_id, id, db, current_user)
