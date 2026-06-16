from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import engine, Base
from src.businesses.router import router as main_router
from src.products.router import router as products_router
from src.sales.router import router as sales_router
from src.analytics.router import router as analytics_router
from src.auth.router import router as auth_router
from src.users.router import router as users_router
from src.debts.router import router as debts_router
from src.customers.router import router as customers_router
from src.celery_tasks.scheduler import start_scheduler, scheduler
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
app.include_router(main_router)
app.include_router(products_router)
app.include_router(sales_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(debts_router)
app.include_router(customers_router)


@app.get("/")
async def root():
    return "API is running"
