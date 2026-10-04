from fastapi import status
from src.businesses import schemas as biz_schemas


def test_create_user(client):
    res = client.post(
        "/users/sign_up",
        json={
            "name": "testuser",
            "email": "testuser@gmail.com",
            "password": "Testpass123",
            "phone": "0244556677"
        }
    )
    assert res.status_code == status.HTTP_201_CREATED


def test_create_user_cannot_self_assign_role(client):
    """A signup must never be able to choose its own role."""
    res = client.post(
        "/users/sign_up",
        json={
            "name": "sneaky",
            "email": "sneaky@gmail.com",
            "password": "Testpass123",
            "phone": "0244000111",
            "role": "super_admin",
        },
    )
    # extra="forbid" rejects the smuggled field instead of silently dropping it
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "role" in res.text


def test_signup_defaults_to_user_role(client):
    """Omitting role yields the lowest-privilege role."""
    res = client.post(
        "/users/sign_up",
        json={
            "name": "plainuser",
            "email": "plainuser@gmail.com",
            "password": "Testpass123",
            "phone": "0244000222",
        },
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["role"] == "user"


def test_create_business(authorized_user_client):
    res = authorized_user_client.post(
        "/businesses/create",
        json={"name": "TestBiz"}
    )
    assert res.status_code == status.HTTP_201_CREATED


def test_get_business(authorized_user_client, authorized_user_client_cre_bus):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(f"/businesses/{business_id}")
    assert res.status_code == status.HTTP_200_OK
    res_data = biz_schemas.BusinessWithMemberCount(**res.json())
    assert res_data.business.business_id == business_id


def test_get_business_not_found(authorized_sup_client):
    res = authorized_sup_client.get("/businesses/9999")
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_create_product(authorized_user_client, authorized_user_client_cre_bus):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.post(
        f"/products/{business_id}",
        json={
            "name": "TestProduct",
            "price": 100.0,
            "cost_price": 50.0,
            "quantity": 10
        }
    )
    assert res.status_code == status.HTTP_201_CREATED
    product = res.json()
    assert product["name"] == "TestProduct"


def test_get_products(authorized_user_client, authorized_user_client_cre_bus, test_products_create):
    business_id = authorized_user_client_cre_bus[0].business_id
    res = authorized_user_client.get(f"/products/{business_id}")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 3
