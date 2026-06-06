from sqlalchemy.orm import Session
from app import database, models
from app.jobs import email_report
from app import schemas
from app.services.sale_service import get_member
from sqlalchemy import func, cast, Date
from fastapi import HTTPException, status, Depends
from datetime import datetime, date

def date_validator(date, end_date):
    if not date or not end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both start date and end date must be provided")
    today = datetime.utcnow().date()
    if date > today or end_date > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot retrieve future data")
    if end_date < date:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="End date cannot be before start date")
    

def view_profit(
                business_id,
                db:Session, 
                current_user, date: date | None = None, 
                end_date: date| None = None):
    
    if current_user.role not in [
        models.RoleEnum.admin, 
        models.RoleEnum.super_admin
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Unauthorized to perform this action")
    
    if date and end_date:
        date_validator(date, end_date)
    
    profit = (
        db.query(
            func.sum(models.Sale.profit).label("total_profit"),
            func.sum(models.Sale.total_amount).label("revenue"),
            func.sum(models.Sale.total_amount - models.Sale.profit).label("total_cost")
        )
        .filter(models.Sale.business_id == business_id)
        .filter(cast(models.Sale.created_at, Date) >= date)
        .filter(cast(models.Sale.created_at, Date) <= end_date)
        .first()
    )
    
    if not profit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"There is no profit margin for any sales between the {date} and {end_date}")

    total_profit, revenue, total_cost = profit

    return {
        "profit": float(total_profit or 0.0),
        "revenue": float(revenue or 0.0),
        "total_cost": float(total_cost or 0.0),
    }



def get_summery(business_id, db:Session, current_user, date, end_date):
    
    if current_user.role not in [
        models.RoleEnum.admin, 
        models.RoleEnum.super_admin,
        models.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    query = (
        db.query( 
                 func.sum(models.SalesItem.quantity).label("sold_quantity") ,
                 func.sum(models.Sale.total_amount).label("total_revenue"),
                 func.sum(models.Sale.profit).label("total_profit"),
                 func.count(models.Sale.sale_id).label("Total_sales")
                 )
        .join(models.SalesItem, models.Sale.sale_id == models.SalesItem.sale_id)
        .filter(models.Sale.business_id == business_id)
    )
    if date:
        query = query.filter(func.date(models.Sale.created_at) >= date)
    if end_date:
        query = query.filter(func.date(models.Sale.created_at) <= end_date)
    summery = query
    result = summery.first()

    sold_quantity = result.sold_quantity or 0
    total_revenue = result.total_revenue or 0.0
    total_profit = result.total_profit or 0.0
    Total_sales = result.Total_sales or 0

    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    cash_q = db.query(func.count(models.Sale.sale_id)).filter(
        models.Sale.business_id == business_id,
        models.Sale.payment_method == models.PaymentMethod.cash,
    )
    if date:
        cash_q = cash_q.filter(func.date(models.Sale.created_at) >= date)
    if end_date:
        cash_q = cash_q.filter(func.date(models.Sale.created_at) <= end_date)
    cash_total = cash_q.scalar() or 0

    momo_q = db.query(func.count(models.Sale.sale_id)).filter(
        models.Sale.business_id == business_id,
        models.Sale.payment_method == models.PaymentMethod.mobile_money,
    )
    if date:
        momo_q = momo_q.filter(func.date(models.Sale.created_at) >= date)
    if end_date:
        momo_q = momo_q.filter(func.date(models.Sale.created_at) <= end_date)
    momo_total = momo_q.scalar() or 0

    card_q = db.query(func.count(models.Sale.sale_id)).filter(
        models.Sale.business_id == business_id,
        models.Sale.payment_method == models.PaymentMethod.card,
    )
    if date:
        card_q = card_q.filter(func.date(models.Sale.created_at) >= date)
    if end_date:
        card_q = card_q.filter(func.date(models.Sale.created_at) <= end_date)
    card_total = card_q.scalar() or 0

    best_q = (
        db.query(
            models.Product.name,
            func.sum(models.SalesItem.quantity).label("total_quantity")
        )
        .join(models.SalesItem, models.Product.product_id == models.SalesItem.product_id)
        .join(models.Sale, models.Sale.sale_id == models.SalesItem.sale_id)
        .filter(models.Sale.business_id == business_id)
    )
    if date:
        best_q = best_q.filter(func.date(models.Sale.created_at) >= date)
    if end_date:
        best_q = best_q.filter(func.date(models.Sale.created_at) <= end_date)
    best_selling = best_q.group_by(models.Product.name).order_by(func.sum(models.SalesItem.quantity).desc()).first()


    best_selling_product = best_selling.name if best_selling else "N/A"
    subject = "Sales Summary Report"
    body={
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
    email = email_report.EmailReport(current_user.email, subject, body)
    email.send()
    return body
    
def check_stock(db:Session, current_user):
    if current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin,
        models.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    member = get_member(db, current_user)
    
    stock = (
        db.query(models.Product)
        .filter(models.Product.business_id == member.business_id)
        .filter(models.Product.quantity <= models.Product.low_stock_threshold)
        .all()
    )
    
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No products are low in stock")
    return stock


def get_debts(business_id, db: Session, current_user):
    if current_user.role not in [
        models.RoleEnum.admin, 
        models.RoleEnum.super_admin,
        models.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="Unauthorized to perform this action")
    
    debts = (
        db.query(func.sum(models.Debt.amount).label("total_debt"))
        .filter(models.Debt.business_id == business_id)
        .filter(models.Debt.is_paid == False)
        .first()
    )
    
    
    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")
    
    return debts