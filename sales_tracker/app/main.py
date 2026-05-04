from sched import scheduler

from fastapi import FastAPI
from sales_tracker.app.database import Base, engine
from sales_tracker.app.routers import business,oauth, products, sales, users, reports, admin_end_report
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sales_tracker.app.services.scheduler import start_scheduler, scheduler
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

@app.get("/")
def root():
    return "API is running "