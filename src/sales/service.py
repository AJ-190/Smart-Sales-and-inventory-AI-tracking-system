from decimal import Decimal
from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, func, cast, Date, delete
from datetime import timedelta, datetime, date, timezone
from src.users import models as um
from src.businesses import models as bm
from src.debts import models as dm
from src.customers.models import Customer
from src.sales import schemas
from src.businesses import models as bm_models, service as biz_service
from src.websocket import socket_manager
from src.notifications import service as notification_service, schemas as notification_schemas



manager = socket_manager.manager


async def add_sale(business_id, post: schemas.SaleCreate, db: AsyncSession, current_user):
    if not post.list_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale must have at least one item")

    total_amount = 0
    total_profit = 0
    total_cost = 0
    items_list = []

    for item in post.list_items:
        result = await db.execute(
            select(bm.Product)
            .where(bm.Product.business_id == business_id)
            .where(bm.Product.product_id == item.product_id)
        )
        product = result.scalars().first()

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
        user_id=current_user.user_id,
        business_id=business_id,
        total_amount=total_amount,
        amount_paid=post.amount_paid,
        payment_method=post.payment_method,
        profit=total_profit,
    )
    db.add(sale)
    await db.flush()

    debt = total_amount - Decimal(str(post.amount_paid))

    for sale_item in items_list:
        sale_data = bm.SalesItem(
            sale_id=sale.sale_id,
            **sale_item
        )
        db.add(sale_data)

    if debt > 0:
        if not post.customer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer ID must be provided for sales with outstanding debt")

        result = await db.execute(
            select(Customer)
            .where(Customer.business_id == business_id)
            .where(Customer.customer_id == post.customer_id)
        )
        check_customer_reg = result.scalars().first()

        if not check_customer_reg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer with the ID: {post.customer_id} not found")

        new_debt = dm.Debt(
            business_id=business_id,
            customer_id=post.customer_id,
            sale_id=sale.sale_id,
            amount=debt,
            due_date=post.due_date or (datetime.now(timezone.utc) + timedelta(days=30))
        )
        db.add(new_debt)

    await db.commit()
    result = await db.execute(
        select(bm.Sale)
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt),
            joinedload(bm.Sale.customer))
        .where(bm.Sale.sale_id == sale.sale_id)
    )
    sale_ = result.scalars().first()

    customer_name = sale_.customer.name if sale_.customer else "Walk-in Customer"
    customer_id = sale_.customer.customer_id if sale_.customer else None

    await manager.broadcast(business_id, f"New sale added for customer {customer_name} (ID: {customer_id})")
    await notification_service.send_notification(
        notification_schemas.SendNotification(
            user_id=current_user.user_id,
            business_id=business_id,
            title="New Sale Added",
            message=f"New sale added for customer {customer_name} (ID: {customer_id}) with total amount {sale_.total_amount}.",
        ),
        business_id,
        db,
        current_user
    )
    return sale_


async def get_sales(business_id: int, db: AsyncSession, current_user, limit: int, skip: int, date: date | None = None):
    today = datetime.now(timezone.utc).date()

    stmt = select(bm.Sale).where(bm.Sale.business_id == business_id)

    if current_user.role == um.RoleEnum.cashier:
        stmt = stmt.where(bm.Sale.user_id == current_user.user_id)

    if date:
        if date > today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date cannot be in the future"
            )
        stmt = stmt.where(
            func.date(bm.Sale.created_at) >= date,
            func.date(bm.Sale.created_at) <= today
        )

    result = await db.execute(
        stmt
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt),
            joinedload(bm.Sale.customer)
        )
        .order_by(bm.Sale.created_at.desc())
        .limit(limit)
        .offset(skip)
    )
    sales = result.unique().scalars().all()

    if not sales:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sales found" + (f" from {date} to {today}" if date else "")
        )

    return sales


async def get_sale(business_id, id, db: AsyncSession, current_user):
    stmt = select(bm.Sale).where(bm.Sale.business_id == business_id)

    if current_user.role == um.RoleEnum.cashier:
        stmt = stmt.where(bm.Sale.user_id == current_user.user_id)

    result = await db.execute(
        stmt
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt),
            joinedload(bm.Sale.customer)
        )
        .where(bm.Sale.sale_id == id)
    )
    sale = result.unique().scalars().first()

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {id} not found")
    return sale


async def delete_sale(business_id, id, db: AsyncSession, current_user):
    result = await db.execute(
        select(bm.Sale)
        .where(bm.Sale.business_id == business_id)
        .where(bm.Sale.sale_id == id)
    )
    sale = result.scalars().first()

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {id} not found")
    
    sale_itmes = (
        await db.execute(
            select(bm_models.SalesItem)
            .where(bm_models.SalesItem.sale_id == sale.sale_id)
            
        )
    ).scalars().all()
    
    for item in sale_itmes:
        product = (
            await db.execute(
                select(bm_models.Product)
                .where(bm_models.Product.product_id == item.product_id)
                )
        ).scalar_one_or_none()
        
        if not product:
            continue
        product.quantity = product.quantity + item.quantity

    debt_result = await db.execute(
        select(dm.Debt).where(dm.Debt.sale_id == sale.sale_id)
    )
    linked_debt = debt_result.scalars().first()
    if linked_debt:
        await db.execute(
            delete(dm.Transactions).where(dm.Transactions.debt_id == linked_debt.debt_id)
        )
    
    await db.delete(sale)
    await db.commit()
    
    await manager.broadcast(business_id, f"Sale with ID: {id} has been deleted")
    await notification_service.send_notification(
        notification_schemas.SendNotification(
            user_id=current_user.user_id,
            business_id=business_id,
            title="Sale Deleted",
            message=f"Sale with ID: {id} has been deleted.",
        ),
        business_id,
        db,
        current_user
    )
    return {"status": "success", "msg": f"sale with the ID: {id} is deleted successfully"}



async def update_sale(business_id, sale_id, sale_data: schemas.SaleUpdate, current_user: um.Users, session: AsyncSession):
    await biz_service.business_authorized_access(current_user, business_id, session)

    stmt = (
        select(bm.Sale)
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt),
            joinedload(bm.Sale.customer))
        .where(bm.Sale.business_id == business_id)
        .where(bm.Sale.sale_id == sale_id)
    )
    if current_user.role == um.RoleEnum.cashier:
        stmt = stmt.where(bm.Sale.user_id == current_user.user_id)

    result = await session.execute(stmt)
    sale = result.unique().scalars().first()

    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sale with the ID: {sale_id} not found")

    updates = sale_data.model_dump(exclude_unset=True)

    if sale_data.list_items is not None:
        for old_item in sale.sales_items:
            product = (
                await session.execute(
                    select(bm.Product).where(bm.Product.product_id == old_item.product_id)
                )
            ).scalar_one_or_none()
            if product:
                product.quantity += old_item.quantity

        total_amount = 0
        total_cost = 0
        total_profit = 0
        new_items = []
        for item in sale_data.list_items:
            product = (
                await session.execute(
                    select(bm.Product)
                    .where(bm.Product.business_id == business_id)
                    .where(bm.Product.product_id == item.product_id)
                )
            ).scalar_one_or_none()
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

            product.quantity -= item.quantity
            subtotal = product.price * item.quantity
            item_cost = (product.cost_price or 0) * item.quantity
            item_profit = subtotal - item_cost

            total_amount += subtotal
            total_cost += item_cost
            total_profit += item_profit
            new_items.append({
                "product_id": product.product_id,
                "quantity": item.quantity,
                "unit_price": product.price,
                "subtotal": subtotal,
                "profit": item_profit,
            })

        for old_item in sale.sales_items:
            await session.delete(old_item)
        await session.flush()
        for item in new_items:
            session.add(bm.SalesItem(sale_id=sale.sale_id, **item))

        sale.total_amount = total_amount
        sale.profit = total_profit
        updates.pop("list_items")

    for key, value in updates.items():
        setattr(sale, key, value)

    debt = sale.total_amount - Decimal(str(sale.amount_paid))
    if debt <= 0:
        if sale.debt:
            await session.delete(sale.debt)
            sale.debt = None
    else:
        if not sale.customer_id:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Customer ID must be provided for sales with outstanding debt")
        if sale.debt:
            sale.debt.amount = debt
            sale.debt.is_paid = False
            sale.debt.customer_id = sale.customer_id
        else:
            session.add(dm.Debt(
                business_id=business_id,
                customer_id=sale.customer_id,
                sale_id=sale.sale_id,
                amount=debt,
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
            ))

    await session.commit()

    result = await session.execute(
        select(bm.Sale)
        .options(
            joinedload(bm.Sale.sales_items),
            joinedload(bm.Sale.debt),
            joinedload(bm.Sale.customer))
        .execution_options(populate_existing=True)
        .where(bm.Sale.sale_id == sale.sale_id)
    )
    sale_ = result.unique().scalars().first()

    await manager.broadcast(business_id, f"Sale with ID: {sale_id} has been updated")
    await notification_service.send_notification(
        notification_schemas.SendNotification(
            user_id=current_user.user_id,
            business_id=business_id,
            title="Sale Updated",
            message=f"Sale with ID: {sale_id} has been updated.",
        ),
        business_id,
        session,
        current_user
    )
    return sale_
        
        