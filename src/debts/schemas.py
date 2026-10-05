from datetime import date as date_type, datetime, time

from pydantic import BaseModel, ConfigDict, field_validator

from src.debts.models import ReminderStatus


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
    customer_email: str | None = None
    customer_phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateDebt(BaseModel):
    fully_paid: bool | None = None
    amount: float | None = None
    note: str | None = None
    due_date: datetime | None = None
    sale_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class Transactions(BaseModel):
    transaction_id: int
    debt_id: int | None = None
    performer_id: int | None = None
    business_id: int
    customer_id: int | None = None
    amount_paid: float
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerTransactions(BaseModel):
    transactions: Transactions
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    customer_address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ScheduleReminder(BaseModel):
    debt_id: int
    customer_id: int
    date: date_type
    time_of_day: time | None = None
    note: str


class ReminderResponse(BaseModel):
    reminder_id: int
    debt_id: int | None = None
    business_id: int | None = None
    customer_id: int | None = None
    date: date_type
    time_of_day: time | None = None
    note: str | None = None
    is_active: bool
    sent_at: datetime | None = None
    status: ReminderStatus = ReminderStatus.PENDING
    attempts: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_unknown_status(cls, value):
        if value is None:
            return ReminderStatus.PENDING
        try:
            return ReminderStatus(value)
        except ValueError:
            return ReminderStatus.PENDING


class UpdateReminder(BaseModel):
    date: date_type | None = None
    time_of_day: time | None = None
    note: str | None = None
    is_active: bool | None = None


class GetReminders(BaseModel):
    debt_id: int | None = None
    customer_id: int | None = None
    date: date_type | None = None
    time_of_day: time | None = None
    note: str | None = None
    is_active: bool | None = None
    status: ReminderStatus | None = None
