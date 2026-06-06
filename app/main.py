from fastapi import FastAPI
from app.database import Base, engine
from app.routers import admin_end_report, business, oauth, products, reports, sales, approvals , customers
from app.routers import users
from contextlib import asynccontextmanager
from app.services.scheduler import start_scheduler, scheduler
from fastapi.middleware.cors import CORSMiddleware
Base.metadata.create_all(bind = engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown()



app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(business.router)
app.include_router(oauth.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(admin_end_report.router)
app.include_router(approvals.router)
app.include_router(customers.router)

@app.get("/")
def root():
    return "API is running"