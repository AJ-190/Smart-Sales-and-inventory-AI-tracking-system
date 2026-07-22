from fastapi import APIRouter, Depends
from src.database import get_db
from src.businesses import schemas, service as biz_service
from src.auth import dependencies as auth_deps
from src.users import models as um


router = APIRouter(prefix="/businesses", tags=['Business'])

roles = {um.RoleEnum.admin, um.RoleEnum.cashier, um.RoleEnum.manager, um.RoleEnum.super_admin, um.RoleEnum.user, um.RoleEnum.viewer}

@router.post("/create", status_code=201, response_model=schemas.BusinessResponse)
async def create_business(post: schemas.BusinessCreate, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await biz_service.add_business(post, db, current_user)


@router.get("/my_businesses", response_model=list[schemas.BusinessWithMemberCount])
async def get_my_bussiness(db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await biz_service.my_businesses(db, current_user)


@router.get("/", response_model=list[schemas.BusinessWithMemberCount])
async def get_businesses(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin]))):
    return await biz_service.get_businesses(db, current_user)


@router.get("/{id}", response_model=schemas.BusinessWithMemberCount)
async def get_business(id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([*roles]))):
    return await biz_service.get_business(id, db, current_user)


@router.put("/{id}", response_model=schemas.BusinessResponse)
async def update_response(id: int, post: schemas.BusinessUpdate, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin]))):
    return await biz_service.update_business(id, post, db, current_user)


@router.delete("/{id}", status_code=204)
async def delete_business(id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin]))):
    return await biz_service.delete_business(id, db, current_user)


@router.get("/business_key/{business_id}", response_model=schemas.Business_key)
async def get_business_key(business_id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await biz_service.get_business_key(business_id, db, current_user)


@router.post("/approvals/send_approval", status_code=201, response_model=schemas.ApprovalsResponseUser)
async def send_approval(post: schemas.ApprovalSend,
                  db=Depends(get_db),
                  current_user=Depends(auth_deps.get_current_user)):
    return await biz_service.send_approval(post, db, current_user)


@router.get("/approvals/get_approvals/{business_id}", response_model=list[schemas.ApprovalsResponse])
async def get_approvals(
    business_id: int,
    status: str | None = None,
    db=Depends(get_db),
    current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await biz_service.get_approvals(business_id, status, db, current_user)


@router.post("/approvals/confirm_approvals/{business_id}", response_model=schemas.ApprovalsResponse)
async def confirm_approval(post: schemas.Direction,
                     business_id: int,
                     db=Depends(get_db),
                     current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await biz_service.con_del_approval(post, business_id, db, current_user)


@router.delete("/leave_business/{business_id}/{member_id}", status_code=204)
async def leave_business(business_id: int,
                         member_id: int,
                         current_user: um.Users = Depends(auth_deps.role_checker([*roles])),
                         session = Depends(get_db)):
    return await biz_service.leave_business(business_id, member_id, current_user, session)


@router.put("/{business_id}/members/{member_id}", response_model=schemas.BusinessMemberResponse)
async def update_business_member(business_id: int, member_id: int, post: schemas.BusinessMemberUpdate,
                                 db=Depends(get_db),
                                 current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await biz_service.update_business_member(business_id, member_id, post, db, current_user)
