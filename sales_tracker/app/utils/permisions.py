# dependencies.py
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

def require_business_role(*allowed_roles):
    def dependency(
        business_id: int,
        db: Session = Depends(database.get_db),
        current_user: models.Users = Depends(get_current_user)
    ):
        # super_admin bypasses everything
        if current_user.role == models.RoleEnum.super_admin:
            business = db.query(models.Business).filter(
                models.Business.business_id == business_id
            ).first()
            if not business:
                raise HTTPException(status_code=404, detail="Business not found")
            return business, None  # no membership needed for super_admin

        membership = (
            db.query(models.BusinessMember)
            .filter(
                models.BusinessMember.user_id == current_user.user_id,
                models.BusinessMember.business_id == business_id,
                models.BusinessMember.is_active == True
            )
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this business")
        if membership.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        return membership.business, membership  # return both so route has context

    return dependency