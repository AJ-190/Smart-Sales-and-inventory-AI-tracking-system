from pydantic import BaseModel, ConfigDict
from datetime import datetime


class DebtResponse(BaseModel):
    debt_id: int
    business_id: int
    customer_id: int
    amount: float
    due_date: datetime
    is_paid: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerDebt(BaseModel):
    customer_debt: float
    customer: list[DebtResponse] = []
    
    model_config = ConfigDict(from_attributes=True)