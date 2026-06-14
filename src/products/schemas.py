from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from src.businesses.schemas import BusinessReposnse


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


class LowStockResponse(BaseModel):
    product_id: int
    name: str
    quantity: int
    low_stock_threshold: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
