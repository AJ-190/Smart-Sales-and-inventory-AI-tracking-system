from fastapi import status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, or_
from datetime import timedelta, datetime, date
from sqlalchemy.orm import joinedload
from src.users import models as um
from src.businesses import models as bm
from src.businesses import schemas
from src.users import schemas as user_schemas
from src.users.service import update_user
from src.celery_tasks.email_report import EmailReport


def get_member(db, current_user):
    member = db.query(um.BusinessMember).filter(um.BusinessMember.business_id == current_user.business_id).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You must create a business before you can perform this action")
    return member


def add_business(post, db: Session, current_user):
    existing = (
        db.query(bm.Business)
        .filter(bm.Business.name == post.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business with the name '{post.name}' is already registered",
        )

    business = bm.Business(name=post.name)
    db.add(business)
    db.flush()

    if current_user.role != um.RoleEnum.super_admin:
        role_update = user_schemas.UserUpdate.model_validate({"role": um.RoleEnum.admin})
        update_user(current_user.user_id, role_update, db, current_user)

    business_member = um.BusinessMember(
        user_id=current_user.user_id,
        role=um.RoleEnum.admin,
        business_id=business.business_id,
    )
    db.add(business_member)
    db.commit()

    return business


def my_businesses(db: Session, current_user):
    businesses = (
        db.query(bm.Business,
                 func.count(um.BusinessMember.member_id).label("members"))
        .outerjoin(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .filter(um.BusinessMember.user_id == current_user.user_id)
        .group_by(bm.Business.business_id)
        .all()
    )
    if not businesses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    return [
        {"business": row[0], "members": row[1]}
        for row in businesses
    ]


def get_businesses(db, current_user):
    if current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    businesses = (
        db.query(
            bm.Business,
            func.count(um.BusinessMember.member_id).label("members")
        )
        .outerjoin(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .group_by(bm.Business.business_id)
        .all()
    )

    if not businesses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business registered yet")
    return [{"business": business, "members": members}
            for business, members in businesses]


def get_business(id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.super_admin, um.RoleEnum.admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    business_data = (
        db.query(bm.Business,
                 func.count(um.BusinessMember.business_id).label("members"))
        .outerjoin(um.BusinessMember,
                   um.BusinessMember.business_id == bm.Business.business_id)
        .filter(bm.Business.business_id == id)
        .group_by(bm.Business.business_id)
    )

    if current_user.role != um.RoleEnum.super_admin:
        business_data = business_data.filter(um.BusinessMember.member_id == current_user.member_id)

    result = business_data.first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No business with id {id} found"
        )

    business, members = result
    return {"business": business, "members": members}


def update_business(id, post, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.super_admin, um.RoleEnum.admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    business = (
        db.query(bm.Business)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .filter(bm.Business.business_id == id)
        .first()
    )

    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    own_business = (
        db.query(bm.Business)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .filter(
            bm.Business.business_id == id,
            um.BusinessMember.member_id == current_user.member_id
        )
        .first()
    )

    if not own_business and current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to update this business")

    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(business, key, value)

    db.commit()
    db.refresh(business)
    return business


def delete_business(id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this transaction")

    business = (
        db.query(bm.Business)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .filter(bm.Business.business_id == id)
    )
    if not business.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Business with the ID: {id} not found")

    user_own_business = business.filter(um.BusinessMember.business_id == current_user.member_id).first()

    if not user_own_business and current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to delete this business")

    db.delete(user_own_business)
    db.commit()
    return {f"Business with the ID:{id} deleted successfully"}


def get_business_key(business_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    key = (
        db.query(bm.Business.business_key)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .filter(bm.Business.business_id == business_id)
        .filter(um.BusinessMember.user_id == current_user.user_id)
        .first()
    )

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No key for business with the ID: {business_id}")

    return key


def add_product(business_id, post: schemas.Productcreate, db: Session, current_user):
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

    existing = db.query(bm.Product).filter(
        bm.Product.business_id == business_id,
        bm.Product.name == post.name
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Product '{post.name}' already exists")

    product = bm.Product(
        **post.model_dump(),
        business_id=business_id
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_Products(business_id, db: Session, current_user, limit, skip, search):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    products = (
        db.query(bm.Product)
        .filter(bm.Product.business_id == business_id)
        .filter(bm.Product.is_active == True)
        .filter(bm.Product.name.contains(search))
        .limit(limit).offset(skip).all()
    )

    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No product found")
    return products


def get_product(business_id, id, db: Session, current_user, limit, skip, search):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager, um.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)

    product = db.query(bm.Product).filter(
        bm.Product.product_id == id,
        bm.Product.business_id == business_id
    ).first()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id} not found")
    return product


def update_product(business_id, id, post: schemas.ProductUpdate, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)
    product = (db.query(bm.Product)
               .filter(bm.Product.business_id == business_id)
               .filter(bm.Product.is_active == True)
               .filter(bm.Product.product_id == id)
               .first()
               )

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID:{id} not found")
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(product, key, value)

    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occurred while updating product")
    return product


def delete_product(business_id, id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    member = get_member(db, current_user)
    product = db.query(bm.Product).filter(bm.Product.product_id == id, bm.Product.business_id == business_id).first()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"status": "success", "message": f"Successfully deleted the product with the ID:{id}"}


def restock(business_id, id, post, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)
    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quantity cannot be negative")

    product = (db.query(bm.Product)
               .filter(bm.Product.business_id == business_id)
               .filter(bm.Product.is_active == True)
               .filter(bm.Product.product_id == id)
               .first()
               )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id}")
    product.quantity += post.quantity
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def low_stock(business_id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)

    products = (db.query(bm.Product)
                .filter(bm.Product.business_id == business_id)
                .filter(bm.Product.is_active == True)
                .filter(bm.Product.quantity < bm.Product.low_stock_threshold)
                .all()
                )
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Product quantity is below its threshold")
    return products


def deactivate(business_id, id, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)
    product = (db.query(bm.Product)
               .filter(bm.Product.business_id == business_id)
               .filter(bm.Product.product_id == id)
               .first()
               )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with the ID: {id} not found")

    if product.is_active:
        product.is_active = False
    else:
        product.is_active = True

    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def date_validator(date, end_date):
    if not date or not end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both start date and end date must be provided")
    today = datetime.utcnow().date()
    if date > today or end_date > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot retrieve future data")
    if end_date < date:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="End date cannot be before start date")


def view_profit(business_id, db: Session, current_user, date: date | None = None, end_date: date | None = None):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    if date and end_date:
        date_validator(date, end_date)

    profit = (
        db.query(
            func.sum(bm.Sale.profit).label("total_profit"),
            func.sum(bm.Sale.total_amount).label("revenue"),
            func.sum(bm.Sale.total_amount - bm.Sale.profit).label("total_cost")
        )
        .filter(bm.Sale.business_id == business_id)
        .filter(cast(bm.Sale.created_at, Date) >= date)
        .filter(cast(bm.Sale.created_at, Date) <= end_date)
        .first()
    )

    if not profit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no profit margin for any sales between the {date} and {end_date}")

    total_profit, revenue, total_cost = profit

    return {
        "profit": float(total_profit or 0.0),
        "revenue": float(revenue or 0.0),
        "total_cost": float(total_cost or 0.0),
    }


def get_summery(business_id, db: Session, current_user, date, end_date):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    query = (
        db.query(
            func.sum(bm.SalesItem.quantity).label("sold_quantity"),
            func.sum(bm.Sale.total_amount).label("total_revenue"),
            func.sum(bm.Sale.profit).label("total_profit"),
            func.count(bm.Sale.sale_id).label("Total_sales")
        )
        .join(bm.SalesItem, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .filter(bm.Sale.business_id == business_id)
    )
    if date:
        query = query.filter(func.date(bm.Sale.created_at) >= date)
    if end_date:
        query = query.filter(func.date(bm.Sale.created_at) <= end_date)
    result = query.first()

    sold_quantity = result.sold_quantity or 0
    total_revenue = result.total_revenue or 0.0
    total_profit = result.total_profit or 0.0
    Total_sales = result.Total_sales or 0

    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    cash_q = db.query(func.count(bm.Sale.sale_id)).filter(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.cash,
    )
    if date:
        cash_q = cash_q.filter(func.date(bm.Sale.created_at) >= date)
    if end_date:
        cash_q = cash_q.filter(func.date(bm.Sale.created_at) <= end_date)
    cash_total = cash_q.scalar() or 0

    momo_q = db.query(func.count(bm.Sale.sale_id)).filter(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.mobile_money,
    )
    if date:
        momo_q = momo_q.filter(func.date(bm.Sale.created_at) >= date)
    if end_date:
        momo_q = momo_q.filter(func.date(bm.Sale.created_at) <= end_date)
    momo_total = momo_q.scalar() or 0

    card_q = db.query(func.count(bm.Sale.sale_id)).filter(
        bm.Sale.business_id == business_id,
        bm.Sale.payment_method == bm.PaymentMethod.card,
    )
    if date:
        card_q = card_q.filter(func.date(bm.Sale.created_at) >= date)
    if end_date:
        card_q = card_q.filter(func.date(bm.Sale.created_at) <= end_date)
    card_total = card_q.scalar() or 0

    best_q = (
        db.query(
            bm.Product.name,
            func.sum(bm.SalesItem.quantity).label("total_quantity")
        )
        .join(bm.SalesItem, bm.Product.product_id == bm.SalesItem.product_id)
        .join(bm.Sale, bm.Sale.sale_id == bm.SalesItem.sale_id)
        .filter(bm.Sale.business_id == business_id)
    )
    if date:
        best_q = best_q.filter(func.date(bm.Sale.created_at) >= date)
    if end_date:
        best_q = best_q.filter(func.date(bm.Sale.created_at) <= end_date)
    best_selling = best_q.group_by(bm.Product.name).order_by(func.sum(bm.SalesItem.quantity).desc()).first()

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


def add_sale(business_id, post: schemas.SaleCreate, db: Session, current_user):
    if current_user.role not in [um.RoleEnum.admin, um.RoleEnum.super_admin,
                                  um.RoleEnum.cashier, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)

    if not post.list_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale must have at least one item")

    total_amount = 0
    total_profit = 0
    total_cost = 0
    items_list = []

    for item in post.list_items:
        product = (
            db.query(bm.Product)
            .filter(bm.Product.business_id == business_id)
            .filter(bm.Product.product_id == item.product_id)
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

        subtotal = product.price * item.quantity
        item_cost = (product.cost_price or 0) * item.quantity
        item_profit = subtotal - item_cost

        total_amount += subtotal
        total_cost += item_cost
        total_profit += item_profit

        product.quantity -= item.quantity

        items_list.append({
            "product_id": product.product_id,
            "quantity": item.quantity,
            "unit_price": product.price,
            "subtotal": subtotal,
            "profit": item_profit,
        })

    sale = bm.Sale(
        user_id=member.user_id,
        business_id=business_id,
        total_amount=total_amount,
        amount_paid=post.amount_paid,
        payment_method=post.payment_method,
        profit=total_profit,
    )
    db.add(sale)
    db.flush()

    debt = total_amount - post.amount_paid

    for sale_item in items_list:
        sale_data = bm.SalesItem(
            sale_id=sale.sale_id,
            **sale_item
        )
        db.add(sale_data)

    if debt > 0:
        if not post.customer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer ID must be provided for sales with outstanding debt")

        check_customer_reg = (
            db.query(bm.Customer)
            .filter(bm.Customer.business_id == business_id)
            .filter(bm.Customer.customer_id == post.customer_id)
            .first()
        )

        if not check_customer_reg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer with the ID: {post.customer_id} not found")

        new_debt = bm.Debt(
            business_id=business_id,
            customer_id=post.customer_id,
            sale_id=sale.sale_id,
            amount=debt,
            due_date=post.due_date or (datetime.utcnow() + timedelta(days=30))
        )
        db.add(new_debt)

    db.commit()
    sale_ = (
        db.query(bm.Sale)
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt))
        .filter(bm.Sale.sale_id == sale.sale_id)
        .first()
    )
    return sale_


def get_sales(business_id: int, db: Session, current_user, limit: int, skip: int, date: date | None = None):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager,
        um.RoleEnum.cashier
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized to perform this action"
        )

    member = get_member(db, current_user)
    today = datetime.utcnow().date()

    query = (
        db.query(bm.Sale)
        .filter(bm.Sale.business_id == business_id)
    )

    if current_user.role == um.RoleEnum.cashier:
        query = query.filter(bm.Sale.user_id == member.user_id)

    if date:
        if date > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date cannot be in the future"
            )
        query = query.filter(
            func.date(bm.Sale.created_at) >= date,
            func.date(bm.Sale.created_at) <= today
        )

    sales = (
        query
        .order_by(bm.Sale.created_at.desc())
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


def get_sale(id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager,
        um.RoleEnum.cashier
    ]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized to perform this action"
        )
    member = get_member(db, current_user)

    query = (
        db.query(bm.Sale)
        .filter(bm.Sale.business_id == member.business_id)
    )

    if current_user.role == um.RoleEnum.cashier:
        query = query.filter(bm.Sale.user_id == member.user_id)

    sale = query.filter(bm.Sale.sale_id == id).first()

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {id} not found")
    return sale


def delete_sale(business_id, id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    sale = (
        db.query(bm.Sale)
        .filter(bm.Sale.business_id == business_id)
        .filter(bm.Sale.sale_id == id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {id} not found")
    db.delete(sale)
    db.commit()
    return {"status": "success", "msg": f"sale with the ID: {id} is deleted successfully"}


def check_stock(db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    member = get_member(db, current_user)

    stock = (
        db.query(bm.Product)
        .filter(bm.Product.business_id == member.business_id)
        .filter(bm.Product.quantity <= bm.Product.low_stock_threshold)
        .all()
    )

    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No products are low in stock")
    return stock


def get_debts(business_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    debts = (
        db.query(func.sum(bm.Debt.amount).label("total_debt"))
        .filter(bm.Debt.business_id == business_id)
        .filter(bm.Debt.is_paid == False)
        .first()
    )

    if not debts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return debts


def send_approval(post, db: Session, current_user):
    check_business_ = (
        db.query(bm.Business)
        .filter(bm.Business.business_key == post.business_key)
        .first()
    )
    if not check_business_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Business with the business key '{post.business_key}' not found")

    existing = (
        db.query(bm.Approvals)
        .join(bm.Business, bm.Business.business_id == bm.Approvals.business_id)
        .filter(bm.Approvals.business_id == check_business_.business_id)
        .filter(bm.Approvals.requester_id == current_user.user_id)
    )
    existing_user = existing.first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already sent an approval request to this business"
        )

    if post.role not in [
        um.RoleEnum.cashier,
        um.RoleEnum.admin,
        um.RoleEnum.manager,
        um.RoleEnum.user,
        um.RoleEnum.viewer
    ]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not found in the business")

    user = bm.Approvals(
        business_id=check_business_.business_id,
        requester_id=current_user.user_id,
        approval_type=bm.ApprovalType.user_join,
        reason=post.reason,
        role=post.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_approvals(business_id, status_, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    approvals = (
        db.query(bm.Approvals)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Approvals.business_id)
        .filter(bm.Approvals.business_id == business_id)
        .filter(um.BusinessMember.user_id == current_user.user_id)
    )
    business_exist = approvals.all()
    if not business_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No approvals found")

    approval_status = (
        approvals
        .filter(bm.Approvals.status == status_)
        .all()
    )

    if not approval_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No approvals found '{status_}'")
    requester_ids = [approval.requester_id for approval in approval_status]

    users = (
        db.query(um.Users)
        .filter(um.Users.user_id.in_(requester_ids))
        .all()
    )

    user_map = {user.user_id: user for user in users}

    result = []
    for approval in approval_status:
        approval.requester = user_map.get(approval.requester_id)
        result.append(approval)

    return result


def con_del_approval(post, business_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.admin,
        um.RoleEnum.super_admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    approval = (
        db.query(bm.Approvals)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Approvals.business_id)
        .filter(um.BusinessMember.business_id == business_id)
        .filter(um.BusinessMember.user_id == current_user.user_id)
    )

    business = approval.first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No business found with the ID: {business_id}")

    approval_user = (
        approval
        .filter(bm.Approvals.approval_id == post.approval_id)
        .first()
    )
    if not approval_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found or already processed")

    if post.dir == 0:
        if approval_user.status == bm.ApprovalStatus.rejected:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already rejected")
        approval_user.status = bm.ApprovalStatus.rejected
        db.add(approval_user)
        db.commit()

    elif post.dir == 1:
        if approval_user.status == bm.ApprovalStatus.approved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already approved")
        approval_user.status = bm.ApprovalStatus.approved
        db.add(approval_user)
        db.commit()

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")

    user = (
        db.query(um.Users)
        .filter(um.Users.user_id == approval_user.requester_id)
        .first()
    )

    approval_user.requester = user
    return approval_user


def role_permission_check(current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager,
        um.RoleEnum.cashier
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Unauthorized to perform this action")


def check_current_user_business(db: Session, current_user, business_id: int):
    business = (
        db.query(um.BusinessMember)
        .filter(um.BusinessMember.user_id == current_user.user_id)
        .filter(um.BusinessMember.business_id == business_id)
        .first()
    )

    if not business:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")


def create_customer(db: Session, current_user, customer: schemas.CustomerCreate, business_id: int):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)
    check_customer_exist = (
        db.query(bm.Customer)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.email == customer.email)
        .first()
    )
    check_customer_exist_phone = (
        db.query(bm.Customer)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.phone == customer.phone)
        .first()
    )

    if check_customer_exist and check_customer_exist.is_active == False:
        for key, value in customer.model_dump(exclude_unset=True).items():
            setattr(check_customer_exist, key, value)
        check_customer_exist.is_active = True
        return check_customer_exist

    if check_customer_exist and check_customer_exist_phone and check_customer_exist.is_active == True:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exist.")

    user = bm.Customer(**customer.model_dump(), business_id=business_id)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_customers(business_id, db: Session, current_user, search, skip, limit):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)
    base_query = (
        db.query(bm.Customer)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.is_active == True)
    )

    if search:
        search_query = f"%{search}%"
        base_query = (
            base_query.filter(
                or_(
                    bm.Customer.name.ilike(search_query),
                    bm.Customer.email.ilike(search_query),
                    bm.Customer.phone.ilike(search_query)
                )
            )
        )
    customers = base_query.order_by(bm.Customer.created_at.desc()).limit(limit).offset(skip).all()
    if not customers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customers found"
        )
    return customers


def get_customer(business_id, customer_id, db: Session, current_user):
    role_permission_check(current_user)

    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(bm.Customer)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.customer_id == customer_id)
        .filter(bm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    return customer


def update_customer(post: schemas.CustomerUpdate, business_id, customer_id, db: Session, current_user):
    role_permission_check(current_user)
    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(bm.Customer)
        .filter(bm.Customer.customer_id == customer_id)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Customer not found")

    base_query = (
        db.query(bm.Customer)
        .filter(bm.Customer.business_id == business_id)
    )

    if customer.email:
        email_check = base_query.filter(bm.Customer.email == customer.email)
        if email_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check email")

    if customer.phone:
        phone_check = base_query.filter(bm.Customer.phone == customer.phone).first()
        if phone_check:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action, check phone_number")
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)

    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(business_id, customer_id, db: Session, current_user):
    if current_user.role not in [
        um.RoleEnum.super_admin,
        um.RoleEnum.admin,
        um.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")

    check_current_user_business(db, current_user, business_id)

    customer = (
        db.query(bm.Customer)
        .filter(bm.Customer.customer_id == customer_id)
        .filter(bm.Customer.business_id == business_id)
        .filter(bm.Customer.is_active == True)
        .first()
    )

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer.is_active = False

    db.commit()

    return {"msg": "Customer is deleted successfully"}
