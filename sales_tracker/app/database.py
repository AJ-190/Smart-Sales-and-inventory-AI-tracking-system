from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sales_tracker.app.core.config import settings


engine = create_engine(settings.DATABASE_URL)
sessionLocal = sessionmaker(autocommit= False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()