
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.core import config
from app.core import security
from fastapi import status, HTTPException, Depends, APIRouter
from app.utils import dependencies
from app import schemas
from app.services.products_service import get_member
from datetime import timedelta, datetime, date
from sqlalchemy import func, cast, Date



def add_sale(business_id, post: schemas.SaleCreate, db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin,
                                  models.RoleEnum.cashier, models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)

    if not post.list_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale must have at least one item")

    total_amount = 0
    total_profit = 0
    total_cost   = 0
    items_list   = []

    # Single loop — validate, calculate, collect
    for item in post.list_items:
        product = (
            db.query(models.Product)
            .filter(models.Product.business_id == business_id)
            .filter(models.Product.product_id == item.product_id)
            .first()
        )

        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Product with ID: {item.product_id} not found")
        if not product.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Product '{product.name}' is not active")
        if item.quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Quantity for '{product.name}' must be greater than zero")
        if item.quantity > product.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Insufficient stock for '{product.name}'. Available: {product.quantity}")

        subtotal    = product.price * item.quantity
        item_cost   = (product.cost_price or 0) * item.quantity
        item_profit = subtotal - item_cost

        total_amount += subtotal
        total_cost   += item_cost
        total_profit += item_profit
        
        product.quantity -= item.quantity  

        items_list.append({
            "product_id": product.product_id,
            "quantity":   item.quantity,
            "unit_price": product.price,
            "subtotal":   subtotal,
            "profit":     item_profit,
        })

    sale = models.Sale(
        user_id        = member.user_id,
        business_id    = business_id,
        total_amount   = total_amount,
        amount_paid    = total_amount,
        payment_method = post.payment_method,
        profit         = total_profit,
    )
    db.add(sale)
    db.flush()

    for sale_item in items_list:
        sale_data = models.SalesItem(
            sale_id = sale.sale_id,
            **sale_item
        )
        db.add(sale_data)

    db.commit()
    db.refresh(sale)
    return sale

def get_sales(
    business_id: int,
    db           : Session,
    current_user,
    limit        : int,
    skip         : int,
    date         : date | None = None, 
):
  
    if current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin,
        models.RoleEnum.manager,
        models.RoleEnum.cashier
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized to perform this action"
        )

    member = get_member(db, current_user)
    today  = datetime.utcnow().date() 


    query = (
        db.query(models.Sale)
        .filter(models.Sale.business_id == business_id)
    )


    if current_user.role == models.RoleEnum.cashier:
        query = query.filter(models.Sale.user_id == member.user_id)


    if date:
        if date > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date cannot be in the future"
            )
        query = query.filter(
            func.date(models.Sale.created_at) >= date,
            func.date(models.Sale.created_at) <= today
        )

   
    sales = (
        query
        .order_by(models.Sale.created_at.desc())  
        .limit(limit)
        .offset(skip)
        .all()
    )

    if not sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sales found" + (f" from {date} to {today}" if date else "")
        )

    return sales



def get_sale(id,db:Session, current_user):
    if current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin,
        models.RoleEnum.manager,
        models.RoleEnum.cashier
    ]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized to perform this action"
        )
    member = get_member(db, current_user)
    
    #base query
    query = (
        db.query(models.Sale)
        .filter(models.Sale.business_id == member.business_id)
    )
    
    if current_user.role == models.RoleEnum.cashier:
        query = (
            query.filter(models.Sale.user_id == member.user_id)
            )
        
    sale = (
        query.filter(models.Sale.sale_id == id).first()
    )
    
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"Sale with the ID: {id} not found")
    return sale


def delete_sale(business_id,id, db:Session, current_user):
    if current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    member = get_member(db, current_user)
    
    sale = (
        db.query(models.Sale)
        .filter(models.Sale.business_id == business_id)
        .filter(models.Sale.sale_id == id)
        .first()
        
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {id} not found")
    db.delete(sale)
    db.commit()
    return {"status": "success", "msg": f"sale with the ID: {id} is deleted successfully "}




