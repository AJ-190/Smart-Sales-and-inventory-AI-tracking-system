from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.errors.handlers import custom_http_exception_handler
from src.db.database import engine, Base, get_db
from src.middleware.auth_middleware import auth_middleware
from src.businesses.router import router as main_router
from src.businesses import service as biz_service
from src.products.router import router as products_router
from src.sales.router import router as sales_router
from src.analytics.router import router as analytics_router
from src.auth.router import router as auth_router
from src.users.router import router as users_router
from src.notifications.router import router as notifications_router
from src.db.redis import get_redis_client
from src.debts.router import router as debts_router
from src.customers.router import router as customers_router
from src.auth import dependencies as auth_deps
from src.users import models as um
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await get_redis_client()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(auth_middleware)
app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler)
app.include_router(main_router)
app.include_router(products_router)
app.include_router(notifications_router)
app.include_router(sales_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(debts_router)
app.include_router(customers_router)


@app.get("/")
async def root():
    return "API is running"


@app.post("/leave_business/{business_id}")
async def leave_business_self(
    business_id: int,
    current_user: um.Users = Depends(auth_deps.get_current_user),
    session=Depends(get_db),
):
    return await biz_service.leave_business(business_id, current_user.user_id, current_user, session)

