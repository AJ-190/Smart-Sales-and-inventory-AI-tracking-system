from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional
from datetime import date, time



class AddDebt(BaseModel):
    amount: float
    note: str 
    due_date: datetime 

class DebtResponse(BaseModel):
    debt_id: int
    business_id: int
    customer_id: int
    amount: float
    due_date: datetime
    is_paid: bool

    model_config = ConfigDict(from_attributes=True)



class CustomerDebt(BaseModel):
    debt: DebtResponse
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
    

    
class UpdateDebt(BaseModel):
    fully_paid: bool | None = None
    amount: float | None = None
    note: str | None = None
    due_date: datetime | None = None
    sale_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    
class Transactions(BaseModel):
    transaction_id: int
    debt_id: int
    performer_id: int
    business_id: int
    customer_id: Optional[int] = None
    amount_paid: float
    note: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CustomerTransactions(BaseModel):
    transactions: Transactions
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    
    
    
class scheduleReminder(BaseModel):
    debt_id: int
    customer_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time_of_day: Optional[time] = None
    note: str
    

class ReminderResponse(BaseModel):
    reminder_id: int
    debt_id: int
    business_id: int
    customer_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time_of_day: Optional[time] = None
    note: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class UpdateReminder(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time_of_day: Optional[time] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None

    
    
class GetReminders(BaseModel):
    debt_id: Optional[int] = None
    customer_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time_of_day: Optional[time] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None