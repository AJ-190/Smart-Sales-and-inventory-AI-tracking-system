from sched import scheduler
from fastapi import FastAPI
from app.database import Base, engine
from app.routers import admin_end_report, business, oauth, products, reports, sales, approvals
from app.routers import users
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.scheduler import start_scheduler, scheduler
Base.metadata.create_all(bind = engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.include_router(business.router)
app.include_router(oauth.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(admin_end_report.router)
app.include_router(approvals.router)

@app.get("/")
def root():
    return "API is running"