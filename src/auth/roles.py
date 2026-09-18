from src.users import models as um


ALL_ROLES = {
    um.RoleEnum.admin,
    um.RoleEnum.cashier,
    um.RoleEnum.manager,
    um.RoleEnum.super_admin,
    um.RoleEnum.user,
    um.RoleEnum.viewer,
}