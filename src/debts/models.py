from sqlalchemy import Column, Numeric, String, Boolean, Integer, DateTime, ForeignKey, Time, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.database import Base





class Debt(Base):
    __tablename__ = "debts"

    debt_id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.sale_id", ondelete="SET NULL"), nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    is_paid = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="debts")
    customer = relationship("Customer", back_populates="debts")
    sale = relationship("Sale", back_populates="debt")
    transactions = relationship("Transactions", back_populates="debt", passive_deletes=True)
    reminders = relationship("Reminders", back_populates="debt", passive_deletes=True)


class Transactions(Base):
    __tablename__ = "transactions"
    transaction_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    debt_id = Column(Integer, ForeignKey("debts.debt_id", ondelete="SET NULL"), nullable=True)
    performer_id= Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    business_id=Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    customer_id=Column(Integer, ForeignKey("customers.customer_id", ondelete="SET NULL"), nullable=True)
    amount_paid = Column(Numeric(12, 2), nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    debt = relationship("Debt", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")
    business = relationship("Business", back_populates="transactions")
    performer = relationship("Users", back_populates="transactions")
    
class Reminders(Base):
    __tablename__ = "reminders"
    reminder_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    
    debt_id = Column(Integer, ForeignKey("debts.debt_id", ondelete="SET NULL"), nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id", ondelete="SET NULL"), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    time_of_day = Column(Time, server_default=text("'09:00'"))
    note = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


    debt = relationship("Debt", back_populates="reminders")
    business = relationship("Business", back_populates="reminders")
    customer = relationship("Customer", back_populates="reminders")
    