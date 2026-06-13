import enum
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    user = "user"
    manager = "manager"
    cashier = "cashier"
    viewer = "viewer"


class Users(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    refresh_token = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    password = Column(String, nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.user, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("BusinessMember", back_populates="user", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="user", cascade="all, delete-orphan")
    user_approvals = relationship("Approvals", foreign_keys="Approvals.requester_id", back_populates="requester")
    reviewer_approvals = relationship("Approvals", foreign_keys="Approvals.reviewer_id", back_populates="reviewer")


class BusinessMember(Base):
    __tablename__ = "business_members"

    member_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.business_id"), nullable=False)
    role = Column(SAEnum(RoleEnum), nullable=False, default=RoleEnum.cashier)
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="memberships")
    business = relationship("Business", back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_user_business"),
    )
