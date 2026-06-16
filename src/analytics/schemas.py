from pydantic import BaseModel, ConfigDict


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
