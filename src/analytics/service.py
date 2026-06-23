from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, cast, Date, select
from datetime import datetime, date
from src.users import models as um
from src.businesses import models as bm
from src.businesses.service import get_member
from src.celery_tasks.email_report import EmailReport


def date_validator(date, end_date):
    if not date or not end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both start date and end date must be provided")
    today = datetime.utcnow().date()
    if date > today or end_date > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot retrieve future data")
    if end_date < date:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="End date cannot be before start date")


async def view_profit(business_id, db: AsyncSession, current_user, date: date | None = None, end_date: date | None = None):
    if date and end_date:
        date_validator(date, end_date)

    profit = (
        (await db.execute(
            select(
                func.sum(bm.Sale.profit).label("total_profit"),
                func.sum(bm.Sale.total_amount).label("revenue"),
                func.sum(bm.Sale.total_amount - bm.Sale.profit).label("total_cost")
            )
            .where(bm.Sale.business_id == business_id)
            .where(cast(bm.Sale.created_at, Date) >= date)
            .where(cast(bm.Sale.created_at, Date) <= end_date)
        )).first()
    )

    if not profit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no profit margin for any sales between the {date} and {end_date}")

    total_profit, revenue, total_cost = profit

    return {
        "profit": float(total_profit or 0.0),
        "revenue": float(revenue or 0.0),
        "total_cost": float(total_cost or 0.0),
    }


async def get_summery(business_id, db: AsyncSession, current_user, date, end_date):
    stmt = (
        select(
            func.sum(bm.SalesItem.quantity).label("sold_quantity"),
            func.sum(bm.Sale.total_amount).label("total_revenue"),
            func.sum(bm.Sale.profit).label("total_profit"),
            func.count(bm.Sale.sale_id).label("Total_sales")
        )
        .join(bm.SalesItem, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .where(bm.Sale.business_id == business_id)
    )
    if date:
        stmt = stmt.where(func.date(bm.Sale.created_at) >= date)
    if end_date:
        stmt = stmt.where(func.date(bm.Sale.created_at) <= end_date)
    result = (await db.execute(stmt)).first()

    sold_quantity = result.sold_quantity or 0
    total_revenue = result.total_revenue or 0.0
    total_profit = result.total_profit or 0.0
    Total_sales = result.Total_sales or 0

    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    cash_stmt = select(func.count(bm.Sale.sale_id)).where(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.cash,
    )
    if date:
        cash_stmt = cash_stmt.where(func.date(bm.Sale.created_at) >= date)
    if end_date:
        cash_stmt = cash_stmt.where(func.date(bm.Sale.created_at) <= end_date)
    cash_total = (await db.execute(cash_stmt)).scalar() or 0

    momo_stmt = select(func.count(bm.Sale.sale_id)).where(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.mobile_money,
    )
    if date:
        momo_stmt = momo_stmt.where(func.date(bm.Sale.created_at) >= date)
    if end_date:
        momo_stmt = momo_stmt.where(func.date(bm.Sale.created_at) <= end_date)
    momo_total = (await db.execute(momo_stmt)).scalar() or 0

    card_stmt = select(func.count(bm.Sale.sale_id)).where(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.card,
    )
    if date:
        card_stmt = card_stmt.where(func.date(bm.Sale.created_at) >= date)
    if end_date:
        card_stmt = card_stmt.where(func.date(bm.Sale.created_at) <= end_date)
    card_total = (await db.execute(card_stmt)).scalar() or 0

    best_stmt = (
        select(
            bm.Product.name,
            func.sum(bm.SalesItem.quantity).label("total_quantity")
        )
        .join(bm.SalesItem, bm.Product.product_id == bm.SalesItem.product_id)
        .join(bm.Sale, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .where(bm.Sale.business_id == business_id)
    )
    if date:
        best_stmt = best_stmt.where(func.date(bm.Sale.created_at) >= date)
    if end_date:
        best_stmt = best_stmt.where(func.date(bm.Sale.created_at) <= end_date)
    best_selling = (await db.execute(
        best_stmt.group_by(bm.Product.name).order_by(func.sum(bm.SalesItem.quantity).desc())
    )).first()

    best_selling_product = best_selling.name if best_selling else "N/A"

    body = {
        "date": str(date),
        "end_date": str(end_date),
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_sales": Total_sales,
        "profit_margin": profit_margin,
        "sold_quantity": sold_quantity,
        "cash_total": cash_total,
        "momo_total": momo_total,
        "card_total": card_total,
        "best_selling_product": best_selling_product,
    }

    subject = "Sales Summary Report"
    email = EmailReport(current_user.email, subject, body)
    email.send()

    return body


async def check_stock(db: AsyncSession, current_user):
    member = await get_member(db, current_user)

    stock = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == member.business_id)
            .where(bm.Product.quantity <= bm.Product.low_stock_threshold)
        )).scalars().all()
    )

    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No products are low in stock")
    return stock



