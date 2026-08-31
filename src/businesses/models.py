import uuid
import enum
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.database import Base
from src.users.models import RoleEnum


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    mobile_money = "mobile_money"

class FileFormat(str, enum.Enum):
    csv ="csv"
    excel = "excel"

class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class ApprovalType(str, enum.Enum):
    user_join = "user_join"
    price_change = "price_change"
    refund_deletion = "refund_deletion"
    large_sale = "large_sale"


class Business(Base):
    __tablename__ = "businesses"

    business_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    business_key = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    bio = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("BusinessMember", back_populates="business", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="business")
    sales = relationship("Sale", back_populates="business")
    customers = relationship("Customer", back_populates="business")
    approvals = relationship("Approvals", back_populates="business")
    debts = relationship("Debt", back_populates="business")
    reminders = relationship("Reminders", back_populates="business")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True)
    description = Column(String, nullable=True)
    sku = Column(String, unique=True, nullable=True)
    category = Column(String, nullable=True)
    quantity = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    business = relationship("Business", back_populates="products", lazy="joined")
    sales_items = relationship("SalesItem", back_populates="product")


class Sale(Base):
    __tablename__ = "sales"

    sale_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=True)
    total_amount = Column(Float, default=0.0)
    amount_paid = Column(Float, nullable=False)
    payment_method = Column(String, default="cash")
    profit = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="sales")
    customer = relationship("Customer", back_populates="sales")
    user = relationship("Users", back_populates="sales")
    sales_items = relationship("SalesItem", back_populates="sale", cascade="all, delete-orphan")
    debt = relationship("Debt", back_populates="sale", uselist=False, cascade="all, delete-orphan")


class SalesItem(Base):
    __tablename__ = "sales_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.sale_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    profit = Column(Float, nullable=False)

    product = relationship("Product", back_populates="sales_items")
    sale = relationship("Sale", back_populates="sales_items")




class Approvals(Base):
    __tablename__ = "approvals"

    approval_id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    role        = Column(SAEnum(RoleEnum), nullable=True)
    approval_type = Column(SAEnum(ApprovalType), nullable=False)
    status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.pending)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="approvals")
    requester = relationship("Users", foreign_keys=[requester_id], back_populates="user_approvals")
    reviewer = relationship("Users", foreign_keys=[reviewer_id], back_populates="reviewer_approvals")
