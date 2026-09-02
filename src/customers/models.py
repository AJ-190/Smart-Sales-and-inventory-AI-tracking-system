from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="customers", passive_deletes=True)
    sales = relationship("Sale", back_populates="customer", passive_deletes=True)
    debts = relationship("Debt", back_populates="customer", passive_deletes=True)
    reminders = relationship("Reminders", back_populates="customer", passive_deletes=True)
    transactions = relationship("Transactions", back_populates="customer", passive_deletes=True)