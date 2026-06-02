from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Annotated
from datetime import datetime, date


from pydantic import BaseModel, EmailStr, field_validator

class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        return value

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None


class UsersOut(BaseModel):
    user_id: int
    name: str
    email: str

    
    model_config = ConfigDict(from_attributes=True)
        
class BusinessReposnse(BaseModel):
    business_id: int
    name: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)
        
class BusinessWithMemberCount(BaseModel):
    business: BusinessReposnse
    members: int
    
    model_config = ConfigDict(from_attributes=True)
        
class UserSignUpResponse(BusinessReposnse):
    business_id: Optional[int] = None
    user_id: int
    name: str
    email: str
    role: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)
    

class BusinessCreate(BaseModel):
    name : str

class BusinessReposnse(BaseModel):
    business_id: int
    name: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)
        
class BusinessUpdate(BaseModel):
    name: Optional[str] = None

class Business_Admin(BaseModel):
    password: str

#---Products-----


    

        
class UsersOutUsers(BaseModel):
    business_id: Optional[int] = None
    member_id: Optional[int] = None
    phone: Optional[str] = None
    user_id: Optional[int] = None
    role: str
    name: str
    email: str

    
    model_config = ConfigDict(from_attributes=True)
        
        
class Productcreate(BaseModel): 
    name: str
    price: float
    cost_price: float
    description: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    quantity: int
    low_stock_threshold: Optional[int] = None        


class ProductResponse(BaseModel):
    product_id  : int
    name        : str
    price       : float
    cost_price  : float | None = None
    sku         : str | None = None
    description : str | None = None
    category    : str | None = None
    quantity    : int
    is_active   : bool
    created_at  : datetime
    business    : BusinessReposnse  

    model_config = ConfigDict(from_attributes=True)
        
class Restock(BaseModel):
    quantity: int

    
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    low_stock_threshold: Optional[int] = None
    quantity: Optional[int] = None
    
class MemberOut(BaseModel):
    member_id:   int
    business_id:  int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)
        
#---token------
class TokenData(BaseModel):
    id: int
    

class Token(BaseModel):
    access_token: str
    token_type: str

    
#---sales----


    
class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int
    

class SaleCreate(BaseModel):
    payment_method: str
    list_items: list[SaleItemCreate]
    
    
class SaleItemResponse(BaseModel):
    item_id    : int
    product_id : int
    quantity   : int
    unit_price : float
    subtotal   : float
    profit     : float

    model_config = ConfigDict(from_attributes=True)
    
class SaleResponse(BaseModel):
    sale_id: int
    total_amount: float
    business_id: int
    user_id: int
    amount_paid: float
    payment_method: str
    notes: Optional[str] = None
    created_at: datetime
    sales_items: list[SaleItemResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
        
class ProfitResponse(BaseModel):
    profit:float
    revenue: float


class SaleSummery(BaseModel):
    total_profit: float
    sold_quantity: float
    total_revenue: float
    total_sales: float
    profit_margin: float
    cash_total: float
    momo_total: float
    card_total: float
    best_selling_product: str
    
    model_config = ConfigDict(from_attributes=True)
        
        
class LowStockResponse(BaseModel):
    product_id: int
    name: str
    quantity: int
    low_stock_threshold: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
        

class ApprovalSend(BaseModel):
    business_key: str
    reason: str
    role: str
    
class ApprovalsResponseUser(BaseModel):
    business_id: int
    approval_id: int
    requester_id: int
    approval_type: str
    status: str
    
    
    model_config = ConfigDict(from_attributes=True)
        
class ApprovalsResponse(BaseModel):
    approval_id: int
    business_id: int
    reason: str
    approval_type: str
    status: str
    requester: UsersOut

    model_config = ConfigDict(from_attributes=True)

    
    model_config = ConfigDict(from_attributes=True)
        
class Business_key(BaseModel):
    business_key: str

    model_config = ConfigDict(from_attributes=True)
    
class Direction(BaseModel):
    approval_id: int
    dir: Annotated[int, Field(le=1, ge=0)] 