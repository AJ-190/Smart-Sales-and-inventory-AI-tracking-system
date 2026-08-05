from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from src.users import models as um
from src.customers import models as cm, service as cv
from src.debts import models as dm
from src.businesses import service, models as bm
from src.debts import schemas
from datetime import datetime, date, timedelta



async def add_debt(post: schemas.AddDebt, business_id: int, customer_id: int, session: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)

    result = await session.execute(
        select(cm.Customer)
        .where(cm.Customer.business_id == business_id)
        .where(cm.Customer.customer_id == customer_id)
    )
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer with ID {customer_id} not found in this business")

    if not customer.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer account is deactivated")

    if post.amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")

    new_debt = dm.Debt(
        business_id=business_id,
        customer_id=customer_id,
        amount=post.amount,
        due_date=post.due_date,
        is_paid=False
    )
    session.add(new_debt)
    await session.flush()

    transaction = dm.Transactions(
        debt_id=new_debt.debt_id,
        business_id=business_id,
        customer_id=customer_id,
        performer_id=current_user.user_id,
        amount_paid=0,
        note=post.note
    )
    session.add(transaction)

    await session.commit()
    await session.refresh(new_debt)
    return new_debt


async def get_debts(business_id, db: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, db)
    
    result = await db.execute(
        select(func.sum(dm.Debt.amount).label("total_debt"))
        .where(dm.Debt.business_id == business_id)
        .where(dm.Debt.is_paid == False)
    )
    row = result.first()
    total_debt = row[0] if row and row[0] else None

    if total_debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customers with outstanding debts found")

    return {"total_debt": float(total_debt)}


async def get_customers_with_debt(business_id,
                                  db: AsyncSession, 
                                  current_user, limit:int, 
                                  skip: int, search: str,
                                  amount_gre: float | None = None,
                                  amount_les: float | None = None):
    await service.business_authorized_access(current_user, business_id, db)
    
    base_query = (
        select(
            dm.Debt,
            cm.Customer.name,
            cm.Customer.email,
            cm.Customer.phone,
        )
        .join(cm.Customer, dm.Debt.customer_id == cm.Customer.customer_id)
        .where(cm.Customer.business_id == business_id)
        .where(dm.Debt.is_paid == False)
    )

    if search:
        search_query = f"%{search}%"
        base_query = base_query.where(
            or_(
                cm.Customer.name.ilike(search_query),
                cm.Customer.phone.ilike(search_query),
                cm.Customer.email.ilike(search_query),
                cm.Customer.address.ilike(search_query)
            )
        )

    if amount_gre is not None:
        base_query = base_query.where(dm.Debt.amount >= amount_gre)
    if amount_les is not None:
        base_query = base_query.where(dm.Debt.amount <= amount_les)
        
    result = await db.execute(
        base_query
        .order_by(dm.Debt.created_at.desc())
        .limit(limit)
        .offset(skip)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No customer with an outstanding debt.")
    
    return [
        {
            "debt": row[0],
            "customer_name": row[1],
            "customer_email": row[2],
            "customer_phone": row[3],
        }
        for row in rows
    ]




async def get_customer_with_debt(business_id,customer_id, session: AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)
    
    customer = (await session.execute(
        select(
            dm.Debt,
            cm.Customer.name,
            cm.Customer.email,
            cm.Customer.phone
        )
        .join(cm.Customer, cm.Customer.customer_id == dm.Debt.customer_id)
        .where(dm.Debt.business_id == business_id)
        .where(cm.Customer.customer_id == customer_id)
        .where(dm.Debt.is_paid == False)
        .order_by(dm.Debt.created_at.desc())
        .limit(1)
    )
    ).one_or_none()
    
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return {
        "debt": customer[0],
        "customer_name": customer[1],
        "customer_email": customer[2],
        "customer_phone": customer[3]
    }


async def update_customer_with_debt(post:schemas.UpdateDebt , business_id, customer_id, session:AsyncSession, current_user):
    await service.business_authorized_access(current_user, business_id, session)
    
    debt = (
        await (
            session.execute(
                select(dm.Debt)
                .join(cm.Customer, cm.Customer.customer_id == dm.Debt.customer_id)
                .where(cm.Customer.business_id == business_id)
                .where(dm.Debt.customer_id == customer_id)
                .where(dm.Debt.is_paid == False)
                .order_by(dm.Debt.created_at.asc())
                .limit(1))
        )
    ).scalar_one_or_none()
    
    if not debt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No outstanding debt found for this customer")
    
    original_amount = debt.amount
    paid_amount = 0
    
    sale_to_update = None
    sale_id = post.sale_id or debt.sale_id
    if sale_id:
        sale_result = await session.execute(
            select(bm.Sale).where(bm.Sale.business_id == business_id).where(bm.Sale.sale_id == sale_id)
        )
        sale_to_update = sale_result.scalar_one_or_none()
    
    if post.amount:
        if post.amount <= 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Amount cannot be less than or equal to zero(0)")
        
        if post.amount >= debt.amount:
            paid_amount = debt.amount
            debt.amount = 0
            debt.is_paid = True
        else:
            paid_amount = post.amount
            debt.amount = debt.amount - post.amount
            
    if post.fully_paid:
        paid_amount = debt.amount
        debt.amount = 0
        debt.is_paid = True
        
    if paid_amount > 0:
        if sale_to_update:
            sale_to_update.amount_paid = sale_to_update.amount_paid + paid_amount
        
        transaction = dm.Transactions(business_id=business_id, 
                                customer_id=customer_id,
                                debt_id=debt.debt_id,
                                performer_id=current_user.user_id,
                                amount_paid=paid_amount,
                                note=post.note if post.note else None)
        session.add(transaction)
   
    await session.commit()

    remaining = (
        await session.execute(
            select(dm.Debt)
            .where(dm.Debt.customer_id == customer_id)
            .where(dm.Debt.business_id == business_id)
            .where(dm.Debt.is_paid == False)
        )
    ).scalars().all()

    if remaining:
        latest = remaining[0]
        return {
            "debt": latest,
            "customer_name": (await session.execute(
                select(cm.Customer.name).where(cm.Customer.customer_id == customer_id)
            )).scalar_one(),
            "customer_email": (await session.execute(
                select(cm.Customer.email).where(cm.Customer.customer_id == customer_id)
            )).scalar_one(),
            "customer_phone": (await session.execute(
                select(cm.Customer.phone).where(cm.Customer.customer_id == customer_id)
            )).scalar_one(),
        }

    customer = (await session.execute(
        select(cm.Customer).where(cm.Customer.customer_id == customer_id)
    )).scalar_one()
    return {
        "debt": {
            "debt_id": 0,
            "business_id": business_id,
            "customer_id": customer_id,
            "amount": 0,
            "due_date": debt.due_date,
            "is_paid": True,
        },
        "customer_name": customer.name,
        "customer_email": customer.email,
        "customer_phone": customer.phone,
    }
    
    
async def get_transactions(business_id, customer_id, current_user: um.Users, session: AsyncSession):
    await service.business_authorized_access(current_user, business_id, session)
    
    customer_transaction = (
       await session.execute(
           select(dm.Transactions,
                  cm.Customer.email,
                  cm.Customer.phone,
                  cm.Customer.name,
                  cm.Customer.address)
           .join(cm.Customer, cm.Customer.customer_id == dm.Transactions.customer_id)
           .where(dm.Transactions.business_id == business_id)
           .where(dm.Transactions.customer_id == customer_id)
           .order_by(dm.Transactions.created_at.desc())
       )
   ).all()
    
    return [
        {
            "transactions": t[0],
            "customer_email": t[1],
            "customer_phone": t[2],
            "customer_name": t[3],
            "customer_address": t[4]
        }
        for t in customer_transaction
    ]
            
    

async def set_reminders(business_id, current_user: um.Users, session: AsyncSession, post: schemas.scheduleReminder):
    await service.business_authorized_access(current_user, business_id, session)
    
    customer = await cv.get_customer(business_id, post.customer_id, session, current_user)
    
    
    customer_with_debt = (
        await session.execute(
            select(dm.Debt)
            .where(dm.Debt.business_id == business_id)
            .where(dm.Debt.customer_id == post.customer_id)
            .where(dm.Debt.debt_id == post.debt_id)
        )
    ).scalar_one_or_none()
    
    if not customer_with_debt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No debt found for this customer")
    
    data = post.model_dump()
    data["business_id"] = business_id
    data["debt_id"] = customer_with_debt.debt_id

    if not data.get("start_date"):
        data["start_date"] = customer_with_debt.due_date.date() - timedelta(days=3)

    if not data.get("end_date"):
        data["end_date"] = customer_with_debt.due_date.date()
        
    reminder = dm.Reminders(**data)
    
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder



async def get_reminders(business_id, current_user: um.Users, session: AsyncSession, post: schemas.GetReminders | None = None):
    await service.business_authorized_access(current_user, business_id, session)
    
    post = post or schemas.GetReminders()
    
    reminders = (
        select(dm.Reminders)
        .where(dm.Reminders.business_id == business_id)
    )
    
    if post.customer_id:
        reminders = reminders.where(dm.Reminders.customer_id == post.customer_id)
        
    if post.start_date:
        reminders = reminders.where(func.date(dm.Reminders.start_date) >= post.start_date)
        
    if post.end_date:
        reminders = reminders.where(func.date(dm.Reminders.end_date) <= post.end_date)
        
    result = await session.execute(reminders.order_by(dm.Reminders.created_at.desc()))
    reminders_list = result.scalars().all()
    
    return reminders_list

async def edit_reminder(business_id, reminder_id, current_user: um.Users, session: AsyncSession, post: schemas.UpdateReminder):
    await service.business_authorized_access(current_user, business_id, session)
    
    reminder = (
        await session.execute(
            select(dm.Reminders)
            .where(dm.Reminders.business_id == business_id)
            .where(dm.Reminders.reminder_id == reminder_id)
        )
    ).scalar_one_or_none()
    
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reminder found for this customer")
    
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(reminder, key, value)
        
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def delete_reminder(business_id, reminder_id, current_user: um.Users, session: AsyncSession):
    await service.business_authorized_access(current_user, business_id, session)
    
    reminder = (
        await session.execute(
            select(dm.Reminders)
            .where(dm.Reminders.business_id == business_id)
            .where(dm.Reminders.reminder_id == reminder_id)
        )
    ).scalar_one_or_none()
    
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reminder found for this customer")
    
    await session.delete(reminder)
    await session.commit()
    return reminder

