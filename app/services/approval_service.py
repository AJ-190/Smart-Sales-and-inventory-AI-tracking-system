from app import models, schemas, database
from fastapi import status, HTTPException, Depends
from sqlalchemy.orm import Session



def send_approval(post, db: Session, current_user):


    check_business_ = (
        db.query(models.Business)
        .filter(models.Business.business_key == post.business_key)
        .first()
    )
    if not check_business_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail= f"Business with the business key '{post.business_key}' not found")
    
    existing =(
        db.query(models.Approvals)
        .join(models.Business, models.Business.business_id == models.Approvals.business_id)
        .filter(models.Approvals.business_id == check_business_.business_id)
        .filter(models.Approvals.requester_id == current_user.user_id)

    )
    existing_user = existing.first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="You have already sent an approval request to this business"
        )


    if post.role not in [
        models.RoleEnum.cashier,
        models.RoleEnum.admin,
        models.RoleEnum.manager,
        models.RoleEnum.user,
        models.RoleEnum.viewer
    ]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not fonud in the business")
    
    user = models.Approvals(
    business_id= check_business_.business_id, 
    requester_id= current_user.user_id,
    approval_type= models.ApprovalType.user_join,
    reason=post.reason,
    role=post.role
)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
    
    
    
def get_approvals(business_id,status_, db: Session, current_user):
    if current_user.role not in [
        models.RoleEnum.super_admin,
        models.RoleEnum.admin,
        models.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    approvals = (
        db.query(models.Approvals)
        .join(models.BusinessMember, models.BusinessMember.business_id == models.Approvals.business_id)
        .filter(models.Approvals.business_id == business_id)
        .filter(models.BusinessMember.user_id == current_user.user_id)
        
    )
    business_exist = approvals.all()
    if not business_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No approvals found")
    
    
    approval_status = (
        approvals
        .filter(models.Approvals.status == status_)
        .all()
        
    )
    
    if not approval_status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"No approvals found '{status_}'")
    requester_ids = [approval.requester_id for approval in approval_status]
    
    users = (
        db.query(models.Users)
        .filter(models.Users.user_id.in_(requester_ids))
        .all()
    )
    
    user_map = {user.user_id: user for user in users}
    
    result = []
    for approval in approval_status:
        approval.requester = user_map.get(approval.requester_id)
        result.append(approval)
    
    return result


def con_del_approval(post,business_id, db: Session, current_user):
    if  current_user.role not in [
        models.RoleEnum.admin,
        models.RoleEnum.super_admin,
        models.RoleEnum.manager
    ]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    
    
    approval = (
        db.query(models.Approvals)
        .join(models.BusinessMember, models.BusinessMember.business_id == models.Approvals.business_id)
        .filter(models.BusinessMember.business_id == business_id)
        .filter(models.BusinessMember.user_id == current_user.user_id)


    )
    
    
    business = approval.first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No business found with the ID: {business_id}")
    
    approval_user = (
        approval
        .filter(models.Approvals.approval_id == post.approval_id)
        .first()
    )
    if not approval_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found or already processed")
    

    if post.dir == 0:
        if approval_user.status == models.ApprovalStatus.rejected:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already rejected")
        approval_user.status = models.ApprovalStatus.rejected
        db.add(approval_user)
        db.commit()

    elif post.dir == 1:
        if approval_user.status == models.ApprovalStatus.approved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already approved")
        approval_user.status = models.ApprovalStatus.approved
        db.add(approval_user)
        db.commit()

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")
        
    user = (
        db.query(models.Users)
        .filter(models.Users.user_id == approval_user.requester_id)
        .first()
    )

    approval_user.requester = user
    return approval_user

