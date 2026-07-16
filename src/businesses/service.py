from fastapi import status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from src.users import models as um
from src.businesses import models as bm
from src.businesses import schemas
from src.users import schemas as user_schemas
from src.users.service import update_user
import uuid

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
    stmt = (
        select(bm.Business)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
        .where(bm.Business.business_id == id)
    )
    business = (await db.execute(stmt)).scalars().first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Business with the ID: {id} not found")

    user_own_business = (await db.execute(stmt.where(um.BusinessMember.user_id == current_user.user_id))).scalars().first()

    if not user_own_business and current_user.role != um.RoleEnum.super_admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to delete this business")

    await db.delete(business)
    await db.commit()
    return {f"Business with the ID:{id} deleted successfully"}


async def get_business_key(business_id, db: AsyncSession, current_user):
    business = (
        await db.execute(
            select(bm.Business)
            .join(um.BusinessMember, um.BusinessMember.business_id == bm.Business.business_id)
            .where(bm.Business.business_id == business_id)
            .where(um.BusinessMember.user_id == current_user.user_id)
        )
    ).scalars().first()

    if not business:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail={"msg": "Businesses does not exist"})
    
    key = business.business_key
    business.business_key = str(uuid.uuid4())
    await db.commit()
    return {"business_key": key }


async def send_approval(post, db: AsyncSession, current_user):
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
    stmt = (
        select(bm.Approvals)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Approvals.business_id)
        .where(bm.Approvals.business_id == business_id)
        .where(um.BusinessMember.user_id == current_user.user_id)
    )
    business_exist = (await db.execute(stmt)).scalars().all()
    if not business_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No approvals found")

    approval_status = (await db.execute(stmt.where(bm.Approvals.status == status_))).scalars().all()

    if not approval_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No approvals found '{status_}'")
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
        approval.requester = user_map.get(approval.requester_id)
        result.append(approval)

    return result


async def con_del_approval(post, business_id, db: AsyncSession, current_user):
    from sqlalchemy.orm import selectinload

    stmt = (
        select(bm.Approvals)
        .join(um.BusinessMember, um.BusinessMember.business_id == bm.Approvals.business_id)
        .where(um.BusinessMember.business_id == business_id)
        .where(um.BusinessMember.user_id == current_user.user_id)
    )

    approval_user = (await db.execute(stmt.where(bm.Approvals.approval_id == post.approval_id))).scalars().first()
    if not approval_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found or already processed")

    if post.dir == 0:
        if approval_user.status == bm.ApprovalStatus.rejected:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already rejected")
        approval_user.status = bm.ApprovalStatus.rejected

    elif post.dir == 1:
        if approval_user.status == bm.ApprovalStatus.approved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already approved")
        approval_user.status = bm.ApprovalStatus.approved

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")

    await db.commit()

    result = await db.execute(
        select(bm.Approvals)
        .options(selectinload(bm.Approvals.requester))
        .where(bm.Approvals.approval_id == post.approval_id)
    )
    return result.scalars().first()


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
    