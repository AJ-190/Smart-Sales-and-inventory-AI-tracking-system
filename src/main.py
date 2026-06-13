from fastapi import FastAPI
from src.database import Base, engine
from src.businesses.router import router as main_router
from src.auth.router import router as auth_router
from src.users.router import router as users_router
from src.debts.router import router as debts_router
from contextlib import asynccontextmanager
from src.celery_tasks.scheduler import start_scheduler, scheduler
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)


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

app.include_router(main_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(debts_router)


@app.get("/")
def root():
    return "API is running"
