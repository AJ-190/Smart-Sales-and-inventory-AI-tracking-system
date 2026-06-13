from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Annotated
from datetime import datetime
from src.users.schemas import UsersOut


class BusinessReposnse(BaseModel):
    business_id: int
    name: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class BusinessWithMemberCount(BaseModel):
    business: BusinessReposnse
    members: int

    model_config = ConfigDict(from_attributes=True)


class BusinessCreate(BaseModel):
    name: str


class BusinessUpdate(BaseModel):
    name: Optional[str] = None


class Business_Admin(BaseModel):
    password: str


class Business_key(BaseModel):
    business_key: str

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
    product_id: int
    name: str
    price: float
    cost_price: float | None = None
    sku: str | None = None
    description: str | None = None
    category: str | None = None
    quantity: int
    is_active: bool
    created_at: datetime
    business: BusinessReposnse

    model_config = ConfigDict(from_attributes=True)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    low_stock_threshold: Optional[int] = None
    quantity: Optional[int] = None


class Restock(BaseModel):
    quantity: int


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: int


class SaleCreate(BaseModel):
    payment_method: str
    amount_paid: float
    list_items: list[SaleItemCreate]
    customer_id: Optional[int] = None
    due_date: Optional[datetime] = None


class SaleItemResponse(BaseModel):
    item_id: int
    product_id: int
    quantity: int
    unit_price: float
    subtotal: float
    profit: float

    model_config = ConfigDict(from_attributes=True)


class DebtResponse(BaseModel):
    debt_id: int
    business_id: int
    customer_id: int
    amount: float
    due_date: datetime
    is_paid: bool

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
    debt: DebtResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ProfitResponse(BaseModel):
    profit: float
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


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    customer_id: int
    business_id: int
    name: str
    phone: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class Direction(BaseModel):
    approval_id: int
    dir: Annotated[int, Field(le=1, ge=0)]


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
    requester: "UsersOut"

    model_config = ConfigDict(from_attributes=True)
