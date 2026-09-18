from src.db.database import Base
from sqlalchemy import func, ForeignKey, DateTime, Index, false
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class GroupChatMessages(Base):
    __tablename__ = "group_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.business_id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    is_edited: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_group_chat_messages_business_created", "business_id", "created_at"),
        Index("ix_group_chat_messages_user_id", "user_id"),
    )