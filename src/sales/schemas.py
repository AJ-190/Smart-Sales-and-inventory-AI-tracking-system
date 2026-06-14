from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


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
