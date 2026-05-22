import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db
from app.models import Base
from sqlalchemy.pool import StaticPool
from app.main import app
from fastapi.testclient import TestClient
from app import schemas, models
from app.core.security import access_token


SQLITE_DATABASE = "sqlite://"

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        SQLITE_DATABASE,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool)
    return engine

@pytest.fixture(scope="function")
def session(db_engine):
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)
    
    TestSessionLocal = sessionmaker(
        autocommit=False, 
         autoflush=False, 
        bind=db_engine
        )
    db = TestSessionLocal()
    yield db
    
    db.close()
    
@pytest.fixture(scope="function")
def client(session):
    def overrides_get_db():
        yield session
    app.dependency_overrides[get_db] = overrides_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(client):
    data ={
         "name": "Addy",
         "email": "adysamuel68@gmail.com",
         "password": "passwordY123",
         "phone": "0257524704"}
    
    res = client.post(
        "/users/sign_up", 
        json=data
    )
    post = schemas.UserSignUpResponse(**res.json())
    return post
    
@pytest.fixture
def test_user_1(client):
    data ={
         "name": "Addy",
         "email": "adysamuel67@gmail.com",
         "password": "passwordY123",
         "phone": "0257524708"}
    
    res = client.post(
        "/users/sign_up", 
        json=data
    )
    post = schemas.UserSignUpResponse(**res.json())
    return post



@pytest.fixture
def token(test_user):
    token = access_token({"sub": str(test_user.user_id)})
    return token

@pytest.fixture
def authorized_sup_client(session, token):
    authorized = TestClient(app)  
    authorized.headers = {"Authorization": f"Bearer {token}"}
    return authorized

@pytest.fixture
def token_1(test_user_1):
    token = access_token({"sub": str(test_user_1.user_id)})
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
        created.append(schemas.BusinessReposnse(**res.json()))
    return created

@pytest.fixture
def test_get_businesses(authorized_sup_client,test_business):
    res = authorized_sup_client.get(
        "/businesses/"
    )

    businesses = [schemas.BusinessWithMemberCount(**business) for business in res.json()]
    return businesses
        
@pytest.fixture
def authorized_sup_products_create(authorized_sup_client, test_get_businesses):
    products = [
        {
            
        "name": "WIFI",
        "price": 4000.0,
        "cost_price": 3000.0,
        "quantity": 10
        
        },{
            
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
        authorized_sup_client.post(
            f"/products/{test_get_businesses[0].business_id}"
        )
        created.append(schemas.Productcreate(**product.json()))
        
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
        
        },{
            
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
            json = product
        )
        created.append(schemas.ProductResponse(**res.json()))
    return created

@pytest.fixture
def test_create_sale_cli(authorized_user_client, authorized_user_client_cre_bus, test_products_create):
    sales = [
        {"payment_method": "momo",
         "list_items": [
             {"product_id": test_products_create[0].product_id, "quantity": 2},
             {"product_id": test_products_create[1].product_id, "quantity": 2}
         ]},
        {"payment_method": "momo",
         "list_items": [
             {"product_id": test_products_create[0].product_id, "quantity": 2},
             {"product_id": test_products_create[1].product_id, "quantity": 2}
         ]},
        {"payment_method": "momo",
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
        products.append(schemas.SaleResponse(**res.json()))

    return products

@pytest.fixture
def test_get_business_key(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.get(
        f"/businesses/business_key/{test_get_businesses[0].business.business_id}"
    )
    
    key = schemas.Business_key(**res.json())
    return key.business_key


@pytest.fixture
def test_send_approval(authorized_user_client, test_get_business_key, ):
    approval_data = {"business_key": test_get_business_key, 
         "reason": "I wanna be the manager",
         "role": "manager"
         }
    
    res = authorized_user_client.post(
        f"/approvals/send_approval/",
        json=approval_data
    )
    
    approval = schemas.ApprovalsResponseUser(**res.json())
    return approval


@pytest.fixture
def test_approve_approval_(authorized_sup_client,test_get_businesses, test_send_approval, authorized_user_client_test_businesses):
    res = authorized_sup_client.post(
        f"/approvals/conirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 1}
    )
    
    approval = [schemas.ApprovalsResponse(**approval) for approval in res.json()]
    return approval[0]