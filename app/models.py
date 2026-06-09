import uuid
import enum
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, Enum, UniqueConstraint, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime, date



class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    admin       = "admin"
    user        = "user"
    manager     = "manager"
    cashier     = "cashier"
    viewer      = "viewer"
    
class PaymentMethod(str, enum.Enum):
    cash         = "cash"
    card         = "card"
    mobile_money = "mobile_money"

class ApprovalStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled   = "cancelled"


class ApprovalType(str, enum.Enum):
    user_join       = "user_join"
    price_change    = "price_change"
    refund_deletion = "refund_deletion"
    large_sale      = "large_sale"
    


class Users(Base):
    __tablename__ = "users"

    user_id    = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String, nullable=False)
    email      = Column(String, nullable=False, unique=True)
    refresh_token = Column(String, nullable=True)
    phone      = Column(String, nullable=True)
    password   = Column(String, nullable=False)
    role       = Column(Enum(RoleEnum), default=RoleEnum.user, nullable=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("BusinessMember", back_populates="user", cascade="all, delete-orphan")
    sales              = relationship("Sale", back_populates="user" , cascade="all, delete-orphan")
    user_approvals     = relationship("Approvals", foreign_keys="Approvals.requester_id", back_populates="requester")
    reviewer_approvals = relationship("Approvals", foreign_keys="Approvals.reviewer_id",  back_populates="reviewer")



class Business(Base):
    __tablename__ = "businesses"

    business_id = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String, nullable=False)
    business_key     = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("BusinessMember", back_populates="business", cascade="all, delete-orphan")
    products  = relationship("Product", back_populates="business")
    sales     = relationship("Sale", back_populates="business")
    customers = relationship("Customer", back_populates="business")
    approvals = relationship("Approvals", back_populates="business")
    debts     = relationship("Debt", back_populates="business")

class BusinessMember(Base):
    __tablename__ = "business_members"

    member_id   = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    role        = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.cashier)
    is_active   = Column(Boolean, default=True)
    joined_at   = Column(DateTime(timezone=True), server_default=func.now())

    user     = relationship("Users", back_populates="memberships")
    business = relationship("Business", back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_user_business"),
    )


class Approvals(Base):
    __tablename__ = "approvals"

    approval_id   = Column(Integer, primary_key=True, autoincrement=True)
    business_id   = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    requester_id  = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    reviewer_id   = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    role          = Column(Enum(RoleEnum), nullable=True)
    approval_type = Column(Enum(ApprovalType), nullable=False)
    status        = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending)
    reason        = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    business  = relationship("Business", back_populates="approvals")
    requester = relationship("Users", foreign_keys=[requester_id], back_populates="user_approvals")
    reviewer  = relationship("Users", foreign_keys=[reviewer_id],  back_populates="reviewer_approvals")



class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    name        = Column(String, nullable=False)
    phone       = Column(String, nullable=True)
    email       = Column(String, nullable=True)
    address     = Column(String, nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False, server_default=text("True"))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="customers")
    sales    = relationship("Sale", back_populates="customer")
    debts    = relationship("Debt", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    product_id          = Column(Integer, primary_key=True, autoincrement=True)
    business_id         = Column(Integer, ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    name                = Column(String, nullable=False)
    price               = Column(Float, nullable=False)
    cost_price          = Column(Float, nullable=True)
    description         = Column(String, nullable=True)
    sku         = Column(String, unique=True, nullable=True)
    category            = Column(String, nullable=True)
    quantity            = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    business    = relationship("Business", back_populates="products", lazy="joined")
    sales_items = relationship("SalesItem", back_populates="product")



class Sale(Base):
    __tablename__ = "sales"

    sale_id        = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    business_id    = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    customer_id    = Column(Integer, ForeignKey("customers.customer_id"), nullable=True)
    total_amount   = Column(Float, default=0.0)
    amount_paid    = Column(Float, nullable=False)
    payment_method = Column(String, default="cash")
    profit         = Column(Float, nullable=True)
    notes          = Column(String, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    business    = relationship("Business", back_populates="sales")
    customer    = relationship("Customer", back_populates="sales")
    user        = relationship("Users", back_populates="sales")
    sales_items = relationship("SalesItem", back_populates="sale", cascade="all, delete-orphan")
    debt = relationship("Debt", back_populates="sale", uselist=False, cascade="all, delete-orphan")



class SalesItem(Base):
    __tablename__ = "sales_items"

    item_id    = Column(Integer, primary_key=True, autoincrement=True)
    sale_id    = Column(Integer, ForeignKey("sales.sale_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity   = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal   = Column(Float, nullable=False)
    profit     = Column(Float, nullable=False)

    product = relationship("Product", back_populates="sales_items")
    sale    = relationship("Sale", back_populates="sales_items")
    
    
class Debt(Base):
    __tablename__ = "debts"
    
    debt_id :Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.sale_id"), nullable=True)
    business_id : Mapped[int] = mapped_column(ForeignKey("businesses.business_id"), nullable=False)
    customer_id : Mapped[int] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    amount : Mapped[float] = mapped_column(Float, nullable=False)
    due_date : Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_paid : Mapped[Boolean] = mapped_column(Boolean, default=False)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     
    business = relationship("Business", back_populates="debts")
    customer = relationship("Customer", back_populates="debts")
    sale = relationship("Sale", back_populates="debt")