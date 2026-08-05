from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from src.users import models as um
from src.businesses import models as bm
from src.customers import models as cm
from src.debts import models as dm
from src.businesses import schemas
from src.users import schemas as user_schemas
from src.users.service import update_user


async def get_member(db, current_user):
    member = (
        await db.execute(
            select(um.BusinessMember).where(um.BusinessMember.user_id == current_user.user_id)
        )
    ).scalars().first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You must create a business before you can perform this action")
    return member


async def add_business(post, db: AsyncSession, current_user):
    existing = (
        (
            await db.execute(
                select(bm.Business).where(bm.Business.name == post.name)
            )
        ).scalars().first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business with the name '{post.name}' is already registered",
        )

    business = bm.Business(name=post.name)
    db.add(business)
    await db.flush()

    if current_user.role != um.RoleEnum.super_admin:
        role_update = user_schemas.UserUpdate.model_validate({"role": um.RoleEnum.admin})
        await update_user(current_user.user_id, role_update, db, current_user)

    business_member = um.BusinessMember(
        user_id=current_user.user_id,
        role=um.RoleEnum.admin,
        business_id=business.business_id,
    )
    db.add(business_member)
    await db.commit()

    return business


async def my_businesses(db: AsyncSession, current_user):
    businesses = (
        (
            await db.execute(
                select(
                    bm.Business,
                    func.count(um.BusinessMember.member_id).label("members"),
                )
                .outerjoin(
                    um.BusinessMember,
                    um.BusinessMember.business_id == bm.Business.business_id,
                )
                .where(um.BusinessMember.user_id == current_user.user_id)
                .group_by(bm.Business.business_id)
            )
        ).all()
    )
    if not businesses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    return [
        {"business": row[0], "members": row[1]}
        for row in businesses
    ]


async def get_businesses(db, current_user):
    businesses = (
        (
            await db.execute(
                select(
                    bm.Business,
                    func.count(um.BusinessMember.member_id).label("members"),
                )
                .outerjoin(
                    um.BusinessMember,
                    um.BusinessMember.business_id == bm.Business.business_id,
                )
                .group_by(bm.Business.business_id)
            )
        ).all()
    )

    if not businesses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business registered yet")
    return [{"business": business, "members": members}
            for business, members in businesses]


async def get_business(id, db: AsyncSession, current_user):
    stmt = (
        select(
            bm.Business,
            func.count(um.BusinessMember.business_id).label("members"),
        )
        .outerjoin(
            um.BusinessMember,
            um.BusinessMember.business_id == bm.Business.business_id,
        )
        .where(bm.Business.business_id == id)
        .group_by(bm.Business.business_id)
    )

    if current_user.role != um.RoleEnum.super_admin:
        stmt = stmt.where(um.BusinessMember.user_id == current_user.user_id)

    result = (await db.execute(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No business with id {id} found"
        )

    business, members = result
    return {"business": business, "members": members}


async def update_business(id, post, db: AsyncSession, current_user):
    business = (
        (
            await db.execute(
                select(bm.Business)
                .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
                .where(bm.Business.business_id == id)
            )
        ).scalars().first()
    )

    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    own_business = (
        (
            await db.execute(
                select(bm.Business)
                .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
                .where(
                    bm.Business.business_id == id,
                    um.BusinessMember.user_id == current_user.user_id,
                )
            )
        ).scalars().first()
    )

    if not own_business and current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to update this business")

    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(business, key, value)

    await db.commit()
    await db.refresh(business)
    return business


async def delete_business(id, db: AsyncSession, current_user):
    business = (await db.execute(
        select(bm.Business).where(bm.Business.business_id == id)
    )).scalars().first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Business with the ID: {id} not found")

    if current_user.role != um.RoleEnum.super_admin:
        is_member = (await db.execute(
            select(um.BusinessMember).where(
                um.BusinessMember.business_id == id,
                um.BusinessMember.user_id == current_user.user_id,
            )
        )).scalars().first()
        if not is_member:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to delete this business")

    await db.execute(
        dm.Transactions.__table__.delete().where(dm.Transactions.business_id == id)
    )
    await db.execute(
        dm.Debt.__table__.delete().where(dm.Debt.business_id == id)
    )
    sales_items_stmt = bm.SalesItem.__table__.delete().where(
        bm.SalesItem.sale_id.in_(
            select(bm.Sale.sale_id).where(bm.Sale.business_id == id)
        )
    )
    await db.execute(sales_items_stmt)
    await db.execute(
        bm.Sale.__table__.delete().where(bm.Sale.business_id == id)
    )
    await db.execute(
        cm.Customer.__table__.delete().where(cm.Customer.business_id == id)
    )
    await db.execute(
        um.BusinessMember.__table__.delete().where(um.BusinessMember.business_id == id)
    )

    await db.delete(business)
    await db.commit()
    return {f"Business with the ID:{id} deleted successfully"}


async def get_business_key(business_id, db: AsyncSession, current_user):
    key = (
        (
            await db.execute(
                select(bm.Business.business_key)
                .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
                .where(bm.Business.business_id == business_id)
                .where(um.BusinessMember.user_id == current_user.user_id)
            )
        ).scalars().first()
    )

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No key for business with the ID: {business_id}")

    return {"business_key": key}


async def send_approval(post, db: AsyncSession, current_user):
    with db.no_autoflush:
        check_business_ = (
            (
                await db.execute(
                    select(bm.Business).where(bm.Business.business_key == post.business_key)
                )
            ).scalars().first()
        )
        if not check_business_:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Business with the business key '{post.business_key}' not found")

        stmt = (
            select(bm.Approvals)
            .join(bm.Business, bm.Business.business_id == bm.Approvals.business_id)
            .where(bm.Approvals.business_id == check_business_.business_id)
            .where(bm.Approvals.requester_id == current_user.user_id)
        
        )
        
        
        existing_user = (await db.execute(stmt)).scalars().first()

        if existing_user:
            if existing_user.status == bm.ApprovalStatus.rejected:
                existing_user.status = bm.ApprovalStatus.pending
                await db.commit()
                await db.refresh(existing_user)
                return existing_user

            if existing_user.status == bm.ApprovalStatus.pending:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval sent and pending.")

            if existing_user.status == bm.ApprovalStatus.approved:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already approved.")

        if post.role not in [
            um.RoleEnum.cashier,
            um.RoleEnum.admin,
            um.RoleEnum.manager,
            um.RoleEnum.user,
            um.RoleEnum.viewer
        ]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not found in the business")

        if not current_user.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=" requester_id is required")

        user = bm.Approvals(
            business_id=check_business_.business_id,
            requester_id=current_user.user_id,
            approval_type=bm.ApprovalType.user_join,
            reason=post.reason,
            role=post.role
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def get_approvals(business_id, status_, db: AsyncSession, current_user):
    with db.no_autoflush:
        business = (
            await db.execute(
                select(bm.Business).where(bm.Business.business_id == business_id)
            )
        ).scalars().first()
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

        if current_user.role != um.RoleEnum.super_admin:
            await business_authorized_access(current_user, business_id, db)
        stmt = select(bm.Approvals).where(bm.Approvals.business_id == business_id)

        if status_:
            try:
                status_enum = bm.ApprovalStatus(status_)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {status_}. Must be one of: {[s.value for s in bm.ApprovalStatus]}")
            stmt = stmt.where(bm.Approvals.status == status_enum)

        approval_status = (await db.execute(stmt)).scalars().all()

        if not approval_status:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No approvals found '{status_}'" if status_ else "No approvals found")

        requester_ids = [approval.requester_id for approval in approval_status]

        users = (
            (
                await db.execute(
                    select(um.Users).where(um.Users.user_id.in_(requester_ids))
                )
            ).scalars().all()
        )

        user_map = {user.user_id: user for user in users}

        result = []
        for approval in approval_status:
            result.append({
                "approval_id": approval.approval_id,
                "business_id": approval.business_id,
                "reason": approval.reason,
                "approval_type": str(approval.approval_type.value) if hasattr(approval.approval_type, 'value') else str(approval.approval_type),
                "status": str(approval.status.value) if hasattr(approval.status, 'value') else str(approval.status),
                "requester": user_map.get(approval.requester_id),
            })

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No requests found")
        return result


async def con_del_approval(post: schemas.Direction, business_id, db: AsyncSession, current_user):
    with db.no_autoflush:
        business = (
            await db.execute(
                select(bm.Business).where(bm.Business.business_id == business_id)
            )
        ).scalars().first()
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

        if current_user.role != um.RoleEnum.super_admin:
            await business_authorized_access(current_user, business_id, db)
        approval_user = (
            await db.execute(
                select(bm.Approvals)
                .where(bm.Approvals.business_id == business_id)
                .where(bm.Approvals.approval_id == post.approval_id)
            )
        ).scalars().first()
        if not approval_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found or already processed")

        requester = (
            await db.execute(
                select(um.Users).where(um.Users.user_id == approval_user.requester_id)
            )
        ).scalar_one_or_none()

        if post.dir == 0:
            if approval_user.status == bm.ApprovalStatus.rejected:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already rejected")
            approval_user.status = bm.ApprovalStatus.rejected
            

        elif post.dir == 1:
            if approval_user.status == bm.ApprovalStatus.approved:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already approved")
            approval_user.status = bm.ApprovalStatus.approved
            existing_member = (
                await db.execute(
                    select(um.BusinessMember)
                    .where(um.BusinessMember.user_id == approval_user.requester_id)
                    .where(um.BusinessMember.business_id == approval_user.business_id)
                )
            ).scalar_one_or_none()
            if existing_member:
                existing_member.role = approval_user.role
                existing_member.is_active = True
            else:
                user = um.BusinessMember(role=approval_user.role, user_id=approval_user.requester_id,
                    business_id=approval_user.business_id)
                db.add(user)


        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")
        
        await db.commit()

        return {
            "approval_id": approval_user.approval_id,
            "business_id": approval_user.business_id,
            "reason": approval_user.reason,
            "approval_type": str(approval_user.approval_type.value) if hasattr(approval_user.approval_type, 'value') else str(approval_user.approval_type),
            "status": str(approval_user.status.value) if hasattr(approval_user.status, 'value') else str(approval_user.status),
            "requester": requester,
        }
        
        
async def delete_approval(business_id, approval_id, session: AsyncSession, current_user):
    with session.no_autoflush:
        business = (
            await session.execute(
                select(bm.Business).where(bm.Business.business_id == business_id)
            )
        ).scalars().first()
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
        
        if current_user.role != um.RoleEnum.super_admin:
            await business_authorized_access(current_user, business_id, session)
        
        approval = (
            await session.execute(
                select(bm.Approvals)
                .where(bm.Approvals.business_id == business_id)
                .where(bm.Approvals.approval_id == approval_id)
            )
        ).scalars().first()
        if not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
        
        
        await session.delete(approval)
        await session.commit()
        return {"detail": "Approval deleted successfully"}

async def business_authorized_access(current_user, business_id, db: AsyncSession):
    if current_user.role != bm.RoleEnum.super_admin:
        
        user_access = (
            (await db.execute(
                select(um.BusinessMember)
                .where(um.BusinessMember.user_id == int(current_user.user_id))
                .where(um.BusinessMember.business_id == business_id)
                
            )).scalars().first()
        )
        
        if not user_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is forbidden")
    

    
async def leave_business(business_id, member_id, current_user: um.Users, session: AsyncSession):
    
    await business_authorized_access(current_user, business_id, session)
    
    result = (
        await session.execute(
            select(um.BusinessMember, bm.Approvals)
            .where(um.BusinessMember.business_id == business_id)
            .where(um.BusinessMember.user_id == member_id)
            .join(bm.Approvals, bm.Approvals.requester_id == um.BusinessMember.member_id)
        )
    ).one_or_none()

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                         detail="User not found in the business")

    member_, approvals = result

    
    if not (current_user.user_id == member_.user_id or current_user.role in [um.RoleEnum.super_admin, um.RoleEnum.admin ]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail="Unauthorized to perform this action")
    
    
    approvals.status = bm.ApprovalStatus.rejected
    await session.delete(member_)
    await session.commit()


async def update_business_member(business_id: int, member_id: int, post: schemas.BusinessMemberUpdate, db: AsyncSession, current_user):
    if current_user.role not in [um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to update members")

    if current_user.role != um.RoleEnum.super_admin:
        is_member = (
            await db.execute(
                select(um.BusinessMember)
                .where(um.BusinessMember.business_id == business_id)
                .where(um.BusinessMember.user_id == current_user.user_id)
            )
        ).scalars().first()
        if not is_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this business")

    member = (
        await db.execute(
            select(um.BusinessMember)
            .where(um.BusinessMember.member_id == member_id)
            .where(um.BusinessMember.business_id == business_id)
        )
    ).scalars().first()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this business")

    update_data = post.model_dump(exclude_unset=True)

    if "role" in update_data:
        try:
            role_value = um.RoleEnum(update_data["role"])
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {update_data['role']}. Must be one of: {[r.value for r in um.RoleEnum]}")
        update_data["role"] = role_value

    for key, value in update_data.items():
        setattr(member, key, value)

    await db.commit()
    await db.refresh(member)

    user = (
        await db.execute(
            select(um.Users).where(um.Users.user_id == member.user_id)
        )
    ).scalar_one_or_none()

    return {
        "member_id": member.member_id,
        "user_id": member.user_id,
        "business_id": member.business_id,
        "role": member.role.value if isinstance(member.role, um.RoleEnum) else member.role,
        "is_active": member.is_active,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        "name": user.name if user else None,
        "email": user.email if user else None,
    }
    
    
