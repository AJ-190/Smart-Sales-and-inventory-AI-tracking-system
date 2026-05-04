from fastapi import status, HTTPException , Depends
from sales_tracker.app.core import config, security
from sales_tracker.app import database, models, schemas
from sqlalchemy.orm import Session

from sales_tracker.app.utils import dependencies

def get_member(db, current_user):
    
    member = db.query(models.BusinessMember).filter(models.BusinessMember.business_id == current_user.business_id).first()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You must create a busines before you can perform this action ")
    return member



def add_product(post: schemas.ProductCreate, db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    
    member = get_member(db, current_user)

    if post.price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Price must be greater than 0")

    if post.cost_price is not None and post.cost_price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot be negative")

    if post.cost_price is not None and post.cost_price > post.price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cost price cannot exceed selling price")


    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity cannot be negative")

   
    existing = db.query(models.Product).filter(
        models.Product.business_id == member.business_id,
        models.Product.name == post.name
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Product '{post.name}' already exists")

  
    product = models.Product(
        **post.model_dump(),
        business_id=member.business_id
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def get_Products(db:Session, current_user, limit, skip, search):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager, models.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    

    member = get_member(db, current_user)
    products = (
        db.query(models.Product)
        .filter(models.Product.business_id == member.business_id)
        .filter(models.Product.is_active == True)
        .filter(models.Product.name.contains(search))
        .limit(limit).offset(skip).all()
    )
    
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No product found")
    return products


def get_product(id, db:Session, current_user, limit, skip, search):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager, models.RoleEnum.cashier]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to perform this action")
    
    
    member = get_member(db, current_user)
    
    product =( db.query(models.Product)
              .filter(models.Product.product_id == id, 
                    models.Product.business_id == member.business_id)
              .first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"Product with the ID: {id} not found")
    return product

def update_product(id, post: schemas.ProductUpdate,db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unathorized to perform this action")
    
    member = get_member(db, current_user)
    product = (db.query(models.Product)
               .filter(models.Product.business_id == member.business_id)
               .filter(models.Product.is_active == True)
               .filter(models.Product.product_id == id)
               .first()
               )
    
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"Product with the ID:{id} not found")
    for key, value in post.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
        
    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occured while updating product, sorry for any inconvinience")
    return product


    
def delete_product(id, db: Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin]:
    
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action")
    member = get_member(db, current_user)
    product = db.query(models.Product).filter(models.Product.product_id == id, models.Product.business_id == member.business_id).first()
    
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"status":"success", "message": f"Successfully deletted the product with the ID:{id}"}


def restock(id, post, db:Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin, models.RoleEnum.manager]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unauthorized to perform thsi action")
    
    member = get_member(db, current_user)
    if post.quantity < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quantity cannot be negative")
    
    product = (db.query(models.Product)
               .filter(models.Product.business_id == member.business_id)
               .filter(models.Product.is_active == True)
               .filter(models.Product.product_id == id)
               .first()
               )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= f"Product with the ID: {id}")
    product.quantity += post.quantity
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def low_stock(db:Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unathorized to perfrom this action")
    
    member = get_member(db, current_user)
    
    products =( db.query(models.Product)
              .filter(models.Product.business_id == member.business_id)
              .filter(models.Product.is_active == True)
              .filter(models.Product.quantity < models.Product.low_stock_threshold)
              .all()
              )
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND ,detail="No Product quantity is below it threshold")
    return products

def deactivate(id, db:Session, current_user):
    if current_user.role not in [models.RoleEnum.admin, models.RoleEnum.super_admin]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perfomr this action")
    
    member = get_member(db, current_user)
    product = (db.query(models.Product)
               .filter(models.Product.business_id == member.business_id)
               .filter(models.Product.product_id == id)
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