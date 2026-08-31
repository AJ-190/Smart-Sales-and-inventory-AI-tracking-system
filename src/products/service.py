from fastapi import status, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.users import models as um
from src.businesses import models as bm
from src.products import schemas
from src.businesses.service import get_member
import pandas as pd
import io
import json


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


async def upload_file(file:UploadFile , current_user: um.Users, session: AsyncSession, business_id):
    business_id = _as_int(business_id)

    if not file.filename.lower().endswith((".csv", ".xls", "xlsx")):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Only CSV and excel files are acceptable")

    contents = await file.read()
    filename = file.filename.lower()
    try:
            if filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents))
        
    except Exception as e:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Could not parse the file")
        
    if df.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file contains no data rows")
    
    df = df.where(pd.notnull(df), None)
    
    with open("src/products/column_aliases.json", "r") as  file:
        df_cols: dict = json.load(file)
        
    required_cols = ["name", "price"]
    
    alias_to_cononical = {}
    for cononical, alliases in df_cols.items():
        for allias in alliases:
            alias_to_cononical[allias] = cononical
            
    df.rename(columns=alias_to_cononical, inplace=True)
    
    missing = [c for c in required_cols if not c in df.columns]
    if missing:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Name and price are required coluns")
    
    if df["price"].isnull().any():
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Price column contain null values")
    
    if df['name'].isnull().any():
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Name column contain null values")
    
    df = df.drop_duplicates(subset=['name'], keep="first")
    for _, row in df.iterrows():
        await product_validity(row)
        
        
        existing = (
            await session.execute(select(bm.Product).
                                  where(bm.Product.business_id == business_id)
                                  .where(bm.Product.name == row['name']))
            
        )
        if existing.scalar() is not None:
            continue
        session.add(bm.Product(**row.to_dict(), business_id=business_id))
        
    await session.commit()
    return {"message": "Products uploaded sucessfully"}

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
