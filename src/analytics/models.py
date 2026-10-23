from src.db.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import func





class Report(Base):
    __tablename__ = "report"
    id: Mapped[int] = mapped_column(primary_key=True, )
    