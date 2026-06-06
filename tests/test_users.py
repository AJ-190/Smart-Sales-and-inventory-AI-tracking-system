from app import schemas, models
import pytest

def test_endpoint(client):
    res = client.get("/")  
    assert res.status_code == 200
    
def test_user_create(client):
    data ={
         "name": "Addy",
         "email": "adysamuel68@gmail.com",
         "password": "passwordY123",
         "phone": "0257524704"}
    
    res = client.post(
        "/users/sign_up", 
        json=data
    )
    user = schemas.UserSignUpResponse(**res.json())
    assert user.name == data['name']
    assert user.email == data['email']
    assert user.role == models.RoleEnum.super_admin
    assert res.status_code == 201
    
def test_create_user_duplicate_email(client, test_user):
    data ={
         "name": "Addy",
         "email": "adysamuel68@gmail.com",
         "password": "passwordY123",
         "phone": "0257524704"}

    res = client.post(
        "/users/sign_up", 
        json=data
    )
    
    assert res.status_code == 409
    
def test_login_user(client, test_user):
    res = client.post(
        "/auth/login",
        data={"username": "adysamuel68@gmail.com",
              "password": "passwordY123"})
    
    post = schemas.Token(**res.json())
    assert post.token_type == "bearer"
    assert res.status_code == 200

def test_login_inc_email(client, test_user):
    res = client.post(
        "/auth/login",
        data={"username": "adysamuel67@gmail.com",
              "password": "passwordY123"}
    )
    
    assert res.status_code == 404

@pytest.mark.parametrize("email , password, status_code", [
    ("wronemail@gmail.com", "password123", 404),
    ("adysamuel68@gmail.com", "wrongpassowrd", 401),
    ("wrongemail@gmail.com", "wrongpassword", 404),
    (None, "wrongpassword", 422),
    ("adysamuel67@gmail.com", None, 422)
])
def test_login_inc_password(client, test_user, email, password, status_code):
    res = client.post(
        "/auth/login",
        data={"username": email, "password": password}
    )
    assert res.status_code == status_code
    
def test_get_users(authorized_sup_client, test_user):
    res = authorized_sup_client.get("/users/all_users")

    assert res.status_code == 200
    users = [schemas.UsersOutUsers(**user) for user in res.json()]
    print(users)
    
def test_get_users_no_sup(client, test_user):
    res = client.get(
        "/users/all_users"
    )
    assert res.status_code == 401
    

    
    
