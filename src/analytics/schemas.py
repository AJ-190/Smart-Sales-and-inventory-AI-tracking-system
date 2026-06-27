from pydantic import BaseModel, ConfigDict
from datetime import date


class ProfitResponse(BaseModel):
    profit: float
    revenue: float
    total_cost: float


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


class DashboardResponse(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    total_revenue: float
    total_profit: float
    total_sales: int
    sold_quantity: int
    profit_margin: float
    cash_total: int
    momo_total: int
    card_total: int
    best_selling_product: str
    total_cost: float
    low_stock_count: int
    low_stock_products: list
    total_debt: float
    total_active_products: int
    total_customers: int
