from fastapi import status, HTTPException, UploadFile
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.users import models as um
from src.businesses import models as bm, service as business_service
from src.products import schemas
from fastapi.responses import FileResponse, StreamingResponse
from src.businesses.service import get_member
import pandas as pd
from src.middleware.logging import logger
import io
import httpx
from src.config import get_settings
import json
from datetime import datetime, timezone
from pathlib import Path
from src.gemini import structure_products

logging = logger("Products")

def _ensure_business_id(product, business_id):
    if product.business_id is None:
        product.business_id = business_id


def _as_int(business_id):
    try:
        return int(business_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="business_id must be an integer")


def _normalize_barcode(barcode):
    if barcode is None:
        return None
    normalized = str(barcode).strip()
    return normalized or None


async def _ensure_barcode_available(db, business_id, barcode, exclude_id=None):
    if not barcode:
        return
    query = select(bm.Product).where(
        bm.Product.business_id == business_id,
        bm.Product.barcode == barcode,
    )
    if exclude_id is not None:
        query = query.where(bm.Product.product_id != exclude_id)
    duplicate = (await db.execute(query)).scalars().first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Barcode '{barcode}' already exists for this business",
        )


async def product_validity(post):
    if post.price is not None and post.price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Price must be greater than 0")

    if post.cost_price is not None and post.cost_price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot be negative")

    if (
        post.cost_price is not None
        and post.price is not None
        and post.cost_price > post.price
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot exceed selling price")

    if post.quantity is not None and post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity cannot be negative")



async def _fetch_external_product(bar_code: str):
    API_URL = get_settings().OPENFOOD_API_URL.format(bar_code=bar_code)

    headers = {
        "User-Agent": "BusinessBotGH/1.0 (businessbotgh.com)"
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(API_URL, headers=headers)

            if response.status_code == status.HTTP_404_NOT_FOUND:
                return None

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict) or data.get("status") == 0:
                return None

            product = data.get("product") or {}
            product_name = product.get("product_name")
            if not isinstance(product_name, str) or not product_name.strip():
                return None

            return product_name.strip()

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Open Food Facts returned HTTP {e.response.status_code}"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Open Food Facts"
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Open Food Facts"
        )


async def get_product_by_barcode(business_id, bar_code: str, db: AsyncSession, current_user):
    business_id = _as_int(business_id)
    normalized = _normalize_barcode(bar_code)

    if normalized is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Barcode must not be empty"
        )

    await business_service.business_authorized_access(current_user, business_id, db)

    product = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.barcode == normalized)
            .where(bm.Product.is_active == True)
            .where(bm.Product.is_deleted == False)
        )).scalars().first()
    )

    if product is not None:
        return {
            "found_locally": True,
            "source": "inventory",
            "product": product,
            "suggested_name": None,
        }

    suggestion = await _fetch_external_product(normalized)

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product found for barcode '{normalized}'"
        )

    return {
        "found_locally": False,
        "source": "openfoodfacts",
        "product": None,
        "suggested_name": suggestion,
    }


async def add_product(business_id, post: schemas.Productcreate, db: AsyncSession, current_user):
    await business_service.business_authorized_access(current_user, business_id, db)
    business_id = _as_int(business_id)

    await product_validity(post)
    data = post.model_dump()
    data["barcode"] = _normalize_barcode(data.get("barcode"))

    existing = (
        (await db.execute(
            select(bm.Product).where(
                bm.Product.business_id == business_id,
                bm.Product.name == post.name
            )
        )).scalars().first()
    )

    if existing and existing.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Product '{post.name}' already exists")

    if existing is not None:
        await _ensure_barcode_available(
            db, business_id, data.get("barcode"), exclude_id=existing.product_id
        )
        existing.deleted_at = None
        existing.is_active = True
        existing.price = post.price
        existing.cost_price = post.cost_price
        existing.quantity = post.quantity
        existing.low_stock_threshold = post.low_stock_threshold
        existing.barcode = data.get("barcode")
        db.add(existing)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Barcode '{data.get('barcode')}' already exists for this business"
            )
        await db.refresh(existing)
        return existing

    await _ensure_barcode_available(db, business_id, data.get("barcode"))

    product = bm.Product(
        **data,
        business_id=business_id
    )
    db.add(product)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if data.get("barcode"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Barcode '{data.get('barcode')}' already exists for this business"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product conflicts with an existing record"
        )
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
    

    df = df.astype(object).where(pd.notna(df), None)

    gen_df = df
    

    with open(Path(__file__).resolve().parent / "column_aliases.json", "r") as file:
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

    required_cols = ['name', "price"]
    check_req = [c for c in required_cols if c not in df.columns]

    if check_req:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Price and product name are required columns")

    if "quantity" in df.columns:
        try:
            df["quantity"] = df["quantity"].fillna(0).astype(int)
        except (TypeError, ValueError):
            pass
    df.dropna(subset=['price', 'name'], inplace=True)
    df = df.drop(columns=['business_id', 'product_id', "updated_at", "created_at", "is_active"], errors='ignore')
    print(df.columns)
    dropped_missing = total_rows - len(df)

    rows_before_dedup = len(df)
    df = df.drop_duplicates(subset=['name'], keep="first")
    skipped_duplicates = rows_before_dedup - len(df)

    cols =  {c.name for c in bm.Product.__table__.columns}

    created = 0
    skipped_existing = 0
    
    try:
        
        for _, row in df.iterrows():
            sku = row.get('sku')
            duplicate_filter = bm.Product.name == row['name']
            if sku is not None:
                duplicate_filter = duplicate_filter | (bm.Product.sku == sku)
            product_ext = (
                await session.execute(select(bm.Product)
                                    .where(bm.Product.business_id == business_id)
                                    .where(duplicate_filter))
            ).scalar()

            if product_ext is not None:
                skipped_existing += 1
                continue
            data = {k:x for k, x in row.to_dict().items() if k in cols}

            data['business_id'] = business_id
            session.add(bm.Product(**data))
            created += 1

        await session.flush()

    except Exception as e:
        await session.rollback()

        created = 0
        try:
            result = structure_products(gen_df)
        except Exception as gemini_err:
            logging.error("Product import fallback failed", extra={"error": str(gemini_err)})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Could not read the file. Please check that it contains product data and try again.")
        if isinstance(result, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
        for product in result.products:
            session.add(bm.Product(**product.model_dump(), business_id=business_id))
            created += 1
    await session.commit()
    return {
        "message": "Product stored successfully",
        "created": created,
        "skipped_missing_name_price": dropped_missing,
        "skipped_duplicates": skipped_duplicates,
        "skipped_existing": skipped_existing,
    }

async def export_products(current_user: um.Users, session: AsyncSession, business_id, file_format):
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


    df = pd.DataFrame(products_dicts)

    for col in df.select_dtypes(include=['datetimetz']).columns:
        if df[col].dt.tz is not None:
            df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)

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
            .join(bm.Business, bm.Business.business_id == bm.Product.business_id)
            .where(bm.Product.business_id == business_id)
            .where(bm.Business.is_active == True)
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
    await product_validity(post)

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

    updates = post.model_dump(exclude_unset=True)
    if "barcode" in updates:
        updates["barcode"] = _normalize_barcode(updates["barcode"])
        await _ensure_barcode_available(
            db, business_id, updates["barcode"], exclude_id=product.product_id
        )

    for key, value in updates.items():
        setattr(product, key, value)

    try:
        await db.commit()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        if "barcode" in updates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Barcode '{updates.get('barcode')}' already exists for this business"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product conflicts with an existing record"
        )
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occurred while updating product")
    return product


async def delete_product(
    business_id,
    id,
    db: AsyncSession,
    current_user
):
    await get_member(db, current_user)
    

    business_id = _as_int(business_id)
    

    result = await db.execute(
        select(bm.Product).where(
            bm.Product.product_id == id,
            bm.Product.business_id == business_id,
            bm.Product.is_deleted == False
        )
    )

    product = result.scalars().first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    product.is_deleted = True
    product.deleted_at = datetime.now(timezone.utc)
    product.is_active = False
    await db.commit()

    return {
        "status": "success",
        "message": f"Successfully deleted product with ID: {id}"
    }

async def restock(business_id, id, post, db: AsyncSession, current_user):
    await get_member(db, current_user)
    business_id = _as_int(business_id)
    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quantity cannot be negative")

    product = (
        (await db.execute(
            select(bm.Product)
            .join(bm.Business, bm.Business.business_id == bm.Product.business_id)
            .where(bm.Product.business_id == business_id)
            .where(bm.Business.is_active == True)
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
