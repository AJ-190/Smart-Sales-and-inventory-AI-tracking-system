from fastapi import status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.users import models as um
from src.businesses import models as bm
from src.products import schemas
from src.businesses.service import get_member


async def add_product(business_id, post: schemas.Productcreate, db: AsyncSession, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    if post.price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Price must be greater than 0")

    if post.cost_price is not None and post.cost_price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot be negative")

    if post.cost_price is not None and post.cost_price > post.price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot exceed selling price")

    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity cannot be negative")

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


async def get_Products(business_id, db: AsyncSession, current_user, limit, skip, search):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

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
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    await get_member(db, current_user)

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
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    await get_member(db, current_user)
    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.product_id == id)
        )).scalars().first()
    )

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID:{id} not found")
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
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    await get_member(db, current_user)
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
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unauthorized to perform this action")

    await get_member(db, current_user)
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
    product.quantity += post.quantity
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def low_stock(business_id, db: AsyncSession, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    await get_member(db, current_user)

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
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    await get_member(db, current_user)
    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.product_id == id)
        )).scalars().first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id} not found")

    if product.is_active:
        product.is_active = False
    else:
        product.is_active = True

    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product
