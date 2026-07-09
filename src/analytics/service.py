from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, cast, Date, select
from datetime import datetime, date
from src.users import models as um
from src.businesses import models as bm
from src.debts import models as dm
from src.customers import models as cm
from src.businesses.service import get_member, business_authorized_access
from src.celery_tasks.email_report import EmailReport


def date_validator(date, end_date):
    if not date or not end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both start date and end date must be provided")
    today = datetime.utcnow().date()
    if date > today or end_date > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot retrieve future data")
    if end_date < date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date cannot be before start date")


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


async def get_dashboard(business_id,
                        db: AsyncSession,
                        current_user, 
                        start_date: date | None = None, 
                        end_date: date | None = None):
    await business_authorized_access(current_user, business_id, db)

    if start_date and end_date:
        date_validator(start_date, end_date)

    summary_stmt = (
        select(
            func.sum(bm.SalesItem.quantity).label("sold_quantity"),
            func.sum(bm.Sale.total_amount).label("total_revenue"),
            func.sum(bm.Sale.profit).label("total_profit"),
            func.count(bm.Sale.sale_id).label("Total_sales"),
        )
        .join(bm.SalesItem, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .where(bm.Sale.business_id == business_id)
    )
    if start_date:
        summary_stmt = summary_stmt.where(func.date(bm.Sale.created_at) >= start_date)
    if end_date:
        summary_stmt = summary_stmt.where(func.date(bm.Sale.created_at) <= end_date)

    summary_result = (await db.execute(summary_stmt)).first()
    sold_quantity = int(summary_result.sold_quantity or 0)
    total_revenue = float(summary_result.total_revenue or 0.0)
    total_profit = float(summary_result.total_profit or 0.0)
    Total_sales = int(summary_result.Total_sales or 0)
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    async def payment_count(method):
        stmt = select(func.count(bm.Sale.sale_id)).where(
            bm.Sale.business_id == business_id,
            bm.Sale.payment_method == method,
        )
        if start_date:
            stmt = stmt.where(func.date(bm.Sale.created_at) >= start_date)
        if end_date:
            stmt = stmt.where(func.date(bm.Sale.created_at) <= end_date)
        return int((await db.execute(stmt)).scalar() or 0)

    cash_total = await payment_count(bm.PaymentMethod.cash)
    momo_total = await payment_count(bm.PaymentMethod.mobile_money)
    card_total = await payment_count(bm.PaymentMethod.card)

    best_stmt = (
        select(
            bm.Product.name,
            func.sum(bm.SalesItem.quantity).label("total_quantity"),
        )
        .join(bm.SalesItem, bm.Product.product_id == bm.SalesItem.product_id)
        .join(bm.Sale, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .where(bm.Sale.business_id == business_id)
    )
    if start_date:
        best_stmt = best_stmt.where(func.date(bm.Sale.created_at) >= start_date)
    if end_date:
        best_stmt = best_stmt.where(func.date(bm.Sale.created_at) <= end_date)
    best_selling = (await db.execute(
        best_stmt.group_by(bm.Product.name).order_by(func.sum(bm.SalesItem.quantity).desc())
    )).first()
    best_selling_product = best_selling.name if best_selling else "N/A"

    total_cost = float(
        (await db.execute(
            select(func.sum(bm.Sale.total_amount - bm.Sale.profit))
            .where(bm.Sale.business_id == business_id)
        )).scalar() or 0.0
    )

    low_stock_products = (
        (await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.quantity <= bm.Product.low_stock_threshold)
        )).scalars().all()
    )
    low_stock_list = [
        {"product_id": p.product_id, "name": p.name, "quantity": p.quantity, "low_stock_threshold": p.low_stock_threshold}
        for p in low_stock_products
    ]

    total_debt = float(
        (await db.execute(
            select(func.sum(dm.Debt.amount))
            .where(dm.Debt.business_id == business_id)
            .where(dm.Debt.is_paid == False)
        )).scalar() or 0.0
    )

    total_active_products = int(
        (await db.execute(
            select(func.count(bm.Product.product_id))
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.is_active == True)
        )).scalar() or 0
    )

    total_customers = int(
        (await db.execute(
            select(func.count(cm.Customer.customer_id))
            .where(cm.Customer.business_id == business_id)
        )).scalar() or 0
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_sales": Total_sales,
        "sold_quantity": sold_quantity,
        "profit_margin": profit_margin,
        "cash_total": cash_total,
        "momo_total": momo_total,
        "card_total": card_total,
        "best_selling_product": best_selling_product,
        "total_cost": total_cost,
        "low_stock_count": len(low_stock_list),
        "low_stock_products": low_stock_list,
        "total_debt": total_debt,
        "total_active_products": total_active_products,
        "total_customers": total_customers,
    }
