from src.db.database import Base
from sqlalchemy import func, ForeignKey, DateTime, Index, false, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class GroupChatMessages(Base):
    __tablename__ = "group_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(nullable=False, server_default="", default="")
    attachment_type: Mapped[str | None] = mapped_column(nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(nullable=True)
    attachment_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_edited: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_group_chat_messages_business_created", "business_id", "created_at"),
        Index("ix_group_chat_messages_user_id", "user_id"),
    )


class ChatReadPosition(Base):
    __tablename__ = "chat_read_positions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.business_id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_chat_read_position"),
    )