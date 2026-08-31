from fastapi import status, HTTPException, UploadFile
from sqlalchemy import select, inspect 
from sqlalchemy.ext.asyncio import AsyncSession
from src.users import models as um
from src.businesses import models as bm, service as business_service
from src.products import schemas
from fastapi.responses import FileResponse, StreamingResponse
from src.businesses.service import get_member
import pandas as pd

import io
import json
from datetime import datetime


def _ensure_business_id(product, business_id):
    if product.business_id is None:
        product.business_id = business_id


def _as_int(business_id):
    try:
        return int(business_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="business_id must be an integer")
        

async def product_validity(post):
    if post.price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Price must be greater than 0")

    if post.cost_price is not None and post.cost_price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot be negative")

    if post.cost_price is not None and post.cost_price > post.price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot exceed selling price")

    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity cannot be negative")



async def add_product(business_id, post: schemas.Productcreate, db: AsyncSession, current_user):
    await business_service.business_authorized_access(current_user, business_id, db)
    business_id = _as_int(business_id)
    await product_validity(post)
    existing = (
        (await db.execute(
            select(bm.Product).where(
                bm.Product.business_id == business_id,
                bm.Product.name == post.name
            )
        )).scalars().first()
    )

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Product '{post.name}' already exists")

    product = bm.Product(
        **post.model_dump(),
        business_id=business_id
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def upload_file(file: UploadFile,current_user: um.Users, session: AsyncSession, business_id):
    await business_service.business_authorized_access(current_user, business_id, session)
    business_id = _as_int(business_id)
    
    if not file.filename.endswith((".csv", ".xls", ".xlsx")):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Only csv and excel is acceptable now")
    
    contents = await file.read()
    try:
        
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not parse file")

    df = df.where(pd.notnull(df), None)
    
    with open("src/products/column_aliases.json", "r") as file:
        column_alliases: dict = json.load(file)
        
    def validate_columns(frame: pd.DataFrame):
        cleand_cols = [ str(col).lower().strip() for col in frame.columns]
        if not cleand_cols or any (not column for column in cleand_cols):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File must contains appropriate columns")
        
        if len(set(cleand_cols)) != len(cleand_cols):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File must not contain duplicate columns")
        
    validate_columns(df)
        
    cononical_to_alias = {}
    for col, allias in column_alliases.items():
        for als in allias:
            cononical_to_alias[als] = col
            
    df.rename(columns=cononical_to_alias, inplace=True)
    total_rows = len(df)
    df.dropna(subset=['price', 'name'], inplace=True)
    dropped_missing = total_rows - len(df)
    rows_before_dedup = len(df)
    df = df.drop_duplicates(subset=['name'], keep="first")
    skipped_duplicates = rows_before_dedup - len(df)
    
    
    required_cols = ['name', "price"]
    check_req = [c for c in required_cols if c not in df.columns]
    
    if check_req:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Price and product name are required columns")
    
    cols =  {c.name for c in bm.Product.__table__.columns}   
    
    created = 0
    skipped_existing = 0
    for _, row in df.iterrows():
        product_ext = (
            await session.execute(select(bm.Product)
                                  .where(bm.Product.business_id == business_id)
                                  .where(bm.Product.name == row['name']))
        ).scalar()
        
        if product_ext is not None:
            skipped_existing += 1
            continue
        data = {k:x for k, x in row.to_dict().items() if k in cols}
        data['business_id'] = business_id
        session.add(bm.Product(**data))
        created += 1
        
    await session.commit()
    return {
        "message": "Product stored successfully",
        "created": created,
        "skipped_missing_name_price": dropped_missing,
        "skipped_duplicates": skipped_duplicates,
        "skipped_existing": skipped_existing,
    }

async def export_products(current_user: um.User, session: AsyncSession, business_id, file_format):
    await business_service.business_authorized_access(current_user, business_id, session)
    business_id = _as_int(business_id)
    products = (
        await session.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            
        )
    ).scalars().all()
    
    
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No product found to be exported")
    products_dicts = [
        {c.key: getattr(p, c.key) for c in inspect(p).mapper.column_attrs}
        for p in products
    ]
    
    for d in products_dicts:
        for k, v in d.items():
            if isinstance(v, datetime) and v.tzinfo is not None:
                d[k] = v.replace(tzinfo=None)

    df = pd.DataFrame(products_dicts)
    buffer = io.BytesIO()
    if file_format == bm.FileFormat.csv:
        df.to_csv(buffer, index=False)
        filename = "products.csv"
        media_type = "text/csv"
        
    else:
        df.to_excel(buffer, index=False)

        filename = "products.xlsx"
        media_type =  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
        
async def get_Products(business_id, db: AsyncSession, current_user, limit, skip, search):
    business_id = _as_int(business_id)
    products = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.is_active == True)
            .where(bm.Product.name.contains(search))
            .limit(limit).offset(skip)
        )).scalars().all()
    )

    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No product found")
    return products


async def get_product(business_id, id, db: AsyncSession, current_user, limit, skip, search):
    await get_member(db, current_user)
    business_id = _as_int(business_id)

    product = (
        (await db.execute(
            select(bm.Product).where(
                bm.Product.product_id == id,
                bm.Product.business_id == business_id
            )
        )).scalars().first()
    )

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id} not found")
    return product


async def update_product(business_id, id, post: schemas.ProductUpdate, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)
    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.product_id == id)
        )).scalars().first()
    )

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID:{id} not found")
    _ensure_business_id(product, business_id)
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(product, key, value)

    try:
        await db.commit()
        await db.refresh(product)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occurred while updating product")
    return product


async def delete_product(business_id, id, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)
    product = (
        (await db.execute(
            select(bm.Product).where(
                bm.Product.product_id == id,
                bm.Product.business_id == business_id
            )
        )).scalars().first()
    )

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await db.delete(product)
    await db.commit()
    return {"status": "success", "message": f"Successfully deleted the product with the ID:{id}"}


async def restock(business_id, id, post, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)
    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quantity cannot be negative")

    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.is_active == True)
            .where(bm.Product.product_id == id)
        )).scalars().first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id}")
    _ensure_business_id(product, business_id)
    product.quantity += post.quantity
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def low_stock(business_id, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)

    products = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.is_active == True)
            .where(bm.Product.quantity < bm.Product.low_stock_threshold)
        )).scalars().all()
    )
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Product quantity is below its threshold")
    return products


async def deactivate(business_id, id, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)
    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.product_id == id)
        )).scalars().first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id} not found")

    _ensure_business_id(product, business_id)
    if product.is_active:
        product.is_active = False
    else:
        product.is_active = True

    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product
