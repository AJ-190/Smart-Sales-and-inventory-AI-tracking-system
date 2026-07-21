import pytest
import asyncio
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from src.database import get_db, Base
from src.main import app
from fastapi.testclient import TestClient
from src.auth import utils as auth_utils

import src.users.models
import src.businesses.models
import src.debts.models
import src.customers.models

from src.users import schemas as user_schemas
from src.businesses import schemas as biz_schemas
from src.products import schemas as product_schemas
from src.sales import schemas as sale_schemas
from unittest.mock import patch


@pytest.fixture(scope="session")
def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(init())
    yield engine


@pytest.fixture
def session(async_engine):
    async def reset():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(reset())
    db = async_sessionmaker(bind=async_engine, expire_on_commit=False)()
    yield db


@pytest.fixture(autouse=True)
def setup_redis():
    app.state.redis = AsyncMock()
    app.state.redis.get.return_value = None
    app.state.redis.hgetall = AsyncMock(return_value={})
    app.state.redis.hset = AsyncMock()
    app.state.redis.hincrby = AsyncMock()
    app.state.redis.expire = AsyncMock()
    with patch("src.celery_tasks.otp_task._send_otp_email", new_callable=AsyncMock, return_value=True):
        yield

@pytest.fixture
def client(session):
    def overrides_get_db():
        yield session
    app.dependency_overrides[get_db] = overrides_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(session):
    user = src.users.models.Users(
        name="Addy",
        email="adysamuel68@gmail.com",
        password=auth_utils.hash("passwordY123"),
        phone="0257524704",
        role=src.users.models.RoleEnum.super_admin,
        is_verified=True,
    )

    async def _create():
        session.add(user)
        await session.commit()
        await session.refresh(user)

    asyncio.run(_create())

    return user_schemas.UserSignUpResponse(
        business_id=None,
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@pytest.fixture
def test_user_1(client):
    data = {
        "name": "Addy",
        "email": "adysamuel67@gmail.com",
        "password": "passwordY123",
        "phone": "0257524708"}

    res = client.post(
        "/users/sign_up",
        json=data
    )
    post = user_schemas.UserSignUpResponse(**res.json())
    return post


@pytest.fixture
def token(test_user):
    token = auth_utils.AccessToken({"sub": str(test_user.user_id), "role": test_user.role})
    return token


@pytest.fixture
def authorized_sup_client(session, token):
    def overrides_get_db():
        yield session
    app.dependency_overrides[get_db] = overrides_get_db
    authorized = TestClient(app)
    authorized.headers = {"Authorization": f"Bearer {token}"}
    yield authorized
    app.dependency_overrides.clear()


@pytest.fixture
def token_1(test_user_1):
    token = auth_utils.AccessToken({"sub": str(test_user_1.user_id), "role": test_user_1.role})
    return token


@pytest.fixture
def authorized_user_client(token_1, session):
    def overrides_get_db():
        yield session
    app.dependency_overrides[get_db] = overrides_get_db
    authorized = TestClient(app)
    authorized.headers = {
        **authorized.headers,
        "Authorization": f"Bearer {token_1}"
    }
    yield authorized
    app.dependency_overrides.clear()


@pytest.fixture
def authorized_user_client_cre_bus(authorized_user_client):
    businesses = [
        {"name": "Great"},
        {"name": "under"},
        {"name": "Rate"}
    ]
    created = []
    for business in businesses:
        res = authorized_user_client.post(
            "/businesses/create",
            json=business
        )
        created.append(biz_schemas.BusinessResponse(**res.json()))
    return created


@pytest.fixture
def test_get_businesses(authorized_sup_client, test_business):
    res = authorized_sup_client.get(
        "/businesses/"
    )

    businesses = [biz_schemas.BusinessWithMemberCount(**business) for business in res.json()]
    return businesses


@pytest.fixture
def authorized_sup_products_create(authorized_sup_client, test_get_businesses):
    products = [
        {
            "name": "WIFI",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        }, {
            "name": "Moderm",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        },
        {
            "name": "Bluetooth speaker",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        }

    ]

    created = []
    for product in products:
        res = authorized_sup_client.post(
            f"/products/{test_get_businesses[0].business.business_id}",
            json=product
        )
        created.append(product_schemas.ProductResponse(**res.json()))

    return created


@pytest.fixture
def authorized_user_client_test_businesses(authorized_user_client_cre_bus):
    return authorized_user_client_cre_bus


@pytest.fixture
def test_business(authorized_sup_client):
    businesses = [

        {"name": "Airbnb"},
        {"name": "alter"},
        {"name": "Core.AI"}
    ]

    for business in businesses:
        authorized_sup_client.post(
            "/businesses/create",
            json=business
        )


@pytest.fixture
def test_products_create(authorized_user_client, authorized_user_client_test_businesses):
    products = [
        {
            "name": "Macbook",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        }, {
            "name": "AirForce",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        },
        {
            "name": "AirLander",
            "price": 4000.0,
            "cost_price": 3000.0,
            "quantity": 10

        }

    ]
    created = []
    for product in products:
        res = authorized_user_client.post(
            f"/products/{authorized_user_client_test_businesses[0].business_id}",
            json=product
        )
        created.append(product_schemas.ProductResponse(**res.json()))
    return created


@pytest.fixture
def test_create_sale_cli(authorized_user_client, authorized_user_client_cre_bus, test_products_create):
    sales = [
        {"payment_method": "momo", "amount_paid": 16000,
         "list_items": [
             {"product_id": test_products_create[0].product_id, "quantity": 2},
             {"product_id": test_products_create[1].product_id, "quantity": 2}
         ]},
        {"payment_method": "momo", "amount_paid": 16000,
         "list_items": [
             {"product_id": test_products_create[0].product_id, "quantity": 2},
             {"product_id": test_products_create[1].product_id, "quantity": 2}
         ]},
        {"payment_method": "momo", "amount_paid": 16000,
         "list_items": [
             {"product_id": test_products_create[0].product_id, "quantity": 2},
             {"product_id": test_products_create[1].product_id, "quantity": 2}
         ]}
    ]

    products = []
    for sale in sales:
        res = authorized_user_client.post(
            f"/sales/{authorized_user_client_cre_bus[0].business_id}",
            json=sale
        )
        products.append(sale_schemas.SaleResponse(**res.json()))

    return products


@pytest.fixture
def test_get_business_key(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.get(
        f"/businesses/business_key/{test_get_businesses[0].business.business_id}"
    )

    key = biz_schemas.Business_key(**res.json())
    return key.business_key


@pytest.fixture
def test_send_approval(authorized_user_client, test_get_business_key):
    approval_data = {"business_key": test_get_business_key,
                     "reason": "I wanna be the manager",
                     "role": "manager"
                     }

    res = authorized_user_client.post(
        f"/businesses/approvals/send_approval/",
        json=approval_data
    )

    approval = biz_schemas.ApprovalsResponseUser(**res.json())
    return approval


@pytest.fixture
def test_approve_approval_(authorized_sup_client, test_get_businesses, test_send_approval, authorized_user_client_test_businesses):
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 1}
    )

    return biz_schemas.ApprovalsResponse(**res.json())
