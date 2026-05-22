import pytest
from app import schemas
def test_create_product(authorized_user_client, authorized_user_client_test_businesses):
    product = {
        "name": "Macbook",
        "price": 4000.0,
        "cost_price": 3000.0,
        "quantity": 10
    }
    res = authorized_user_client.post(
        f"/products/{authorized_user_client_test_businesses[0].business_id}",
        json=product
    )
    print(res.json())
    assert res.status_code == 201

    product_res = schemas.ProductResponse(**res.json())
    assert product_res.name == product['name']
    
def test_products_dup_names(authorized_user_client, authorized_user_client_test_businesses):
    product = {
        "name": "Macbook",
        "price": 4000.0,
        "cost_price": 3000.0,
        "quantity": 10
    }
    authorized_user_client.post(
        f"/products/{authorized_user_client_test_businesses[0].business_id}",
        json=product
    )
    res = authorized_user_client.post(
        f"/products/{authorized_user_client_test_businesses[0].business_id}",
        json=product
    )
    
    assert res.status_code == 409
    
def test_get_my_products(authorized_user_client, authorized_user_client_test_businesses, test_products_create):
    
    res = authorized_user_client.get(
        f"/products/{authorized_user_client_test_businesses[0].business_id}"
    )
    
    assert res.status_code == 200
    product_res = [schemas.ProductResponse(**product) for product in res.json()]
    assert product_res[0].name == test_products_create[0].name
    

def test_get_single_product(authorized_user_client, authorized_user_client_test_businesses, test_products_create):
    res = authorized_user_client.get(
        f"/products/{authorized_user_client_test_businesses[0].business_id}/{test_products_create[0].product_id}"
    )
    
    assert res.status_code == 200
    
def test_product_unathorized(authorized_sup_client,test_get_businesses, test_products_create):
    res = authorized_sup_client.get(
        f"/products/{test_get_businesses[0].business.business_id}/{test_products_create[0].product_id}"
    )

    assert res.status_code == 404
def test_product_not_exist(authorized_user_client, authorized_user_client_test_businesses):
    res = authorized_user_client.get(
        f"/products/{authorized_user_client_test_businesses[0].business_id}/404"
    )
    assert res.status_code == 404
    
def test_update_product_price(authorized_user_client,authorized_user_client_test_businesses, test_products_create):
    res = authorized_user_client.put(
        f"/products/{authorized_user_client_test_businesses[0].business_id}/{test_products_create[0].product_id}",
        json={'price': 30000}
    )
    
    assert res.status_code == 200
    product = schemas.ProductResponse(**res.json())
    assert product.price == 30000
    
def test_update_stock_quantity(authorized_user_client,authorized_user_client_test_businesses,test_products_create ):
    res = authorized_user_client.post(
        f"/products/{authorized_user_client_test_businesses[0].business_id}/{test_products_create[0].product_id}/restock",
        json={"quantity":30000}
    )

    assert res.status_code == 200
    product = schemas.ProductResponse(**res.json())
    assert product.product_id == test_products_create[0].product_id
    