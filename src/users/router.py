from fastapi import status, HTTPException, Depends, APIRouter
from src.database import get_db
from src.users import schemas, service as users_service, models as um
from src.auth import dependencies as auth_deps

router = APIRouter(prefix="/users", tags=['Users'])


@router.post("/sign_up", response_model=schemas.UserSignUpResponse, status_code=201)
async def add_user(post: schemas.UserSignUp, db=Depends(get_db)):
    return await users_service.add_user(post, db)


@router.get("/", response_model=list[schemas.UsersOutUsers])
async def get_users(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin]))):
    return await users_service.get_users(db, current_user)


@router.get("/members", response_model=list[schemas.UsersOutUsers])
async def get_members(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await users_service.get_members(db, current_user)


@router.get("/all_users", response_model=list[schemas.UsersOutUsers])
async def get_all_users(db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin]))):
    return await users_service.get_all_users(db, current_user)


@router.get("/me/profile", response_model=schemas.UsersOutUsers)
async def get_my_profile(current_user=Depends(auth_deps.get_current_user)):
    return current_user


@router.get("/{id}", response_model=schemas.UsersOutUsers)
async def get_user(id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await users_service.get_user(id, db, current_user)


@router.put("/{id}", response_model=schemas.UsersOutUsers)
async def update_user(id: int, post: schemas.UserUpdate, db=Depends(get_db), current_user=Depends(auth_deps.get_current_user)):
    return await users_service.update_user(id, post, db, current_user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: int, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin]))):
    return await users_service.delete_user(id, db, current_user)


@router.put("/{id}/activate", response_model=schemas.UserSignUpResponse)
async def activate_user(id, db=Depends(get_db), current_user=Depends(auth_deps.role_checker([um.RoleEnum.super_admin, um.RoleEnum.admin, um.RoleEnum.manager]))):
    return await users_service.activate_user(id, db, current_user)
