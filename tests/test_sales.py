import pytest
from datetime import date, timedelta
from src.sales import schemas

def test_create_sale(authorized_user_client, authorized_user_client_cre_bus, test_products_create):
    res = authorized_user_client.post(
    f"/sales/{authorized_user_client_cre_bus[0].business_id}",
    json={"payment_method": "momo",
          "amount_paid": 16000,
          "list_items":[
             { "product_id": test_products_create[0].product_id, "quantity": 2},
             { "product_id": test_products_create[1].product_id, "quantity": 2}
          ] }
    )
    assert res.status_code == 201
    sale = schemas.SaleResponse(**res.json())
    assert sale.sales_items[0].product_id == test_products_create[0].product_id
    
def test_create_sale_unauthorized(client,authorized_user_client_cre_bus, test_products_create):
    res = client.post(
    f"/sales/{authorized_user_client_cre_bus[0].business_id}",
    json={"payment_method": "momo",
          "list_items":[
             { "product_id": test_products_create[0].product_id, "quantity": 2},
             { "product_id": test_products_create[1].product_id, "quantity": 2}
          ] }
    )
    assert res.status_code == 401
    


def test_sale_no_product(authorized_user_client,authorized_user_client_cre_bus, test_products_create):
    res = authorized_user_client.post(
    f"/sales/{authorized_user_client_cre_bus[0].business_id}",
    json={"payment_method": "momo",
          "amount_paid": 8000,
          "list_items":[
             { "product_id": 7, "quantity": 2},
             { "product_id": 7, "quantity": 2}
          ] }
    )
    
    assert res.status_code == 404
    
def test_sale_quantity_higher(authorized_user_client,authorized_user_client_cre_bus, test_products_create):
    res = authorized_user_client.post(
    f"/sales/{authorized_user_client_cre_bus[0].business_id}",
    json={"payment_method": "momo",
          "amount_paid": 8000,
          "list_items":[
             { "product_id": test_products_create[0].product_id, "quantity": 10000},
             { "product_id": test_products_create[1].product_id, "quantity": 20000}
          ] }
    )
    
    assert res.status_code == 400
    
def test_get_all_sales_for_bus(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        f"/sales/{authorized_user_client_cre_bus[0].business_id}"
    )
    assert res.status_code == 200
    sales = [schemas.SaleResponse(**sale) for sale in res.json()]
    assert len(sales) == len(test_create_sale_cli)
    

def test_get_sales_by_date_more_(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    future_date = (date.today() + timedelta(days=1)).isoformat()
    res = authorized_user_client.get(
        f"/sales/{authorized_user_client_cre_bus[0].business_id}?date={future_date}"
    )
    assert res.status_code == 400
    
def test_get_single_sale(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.get(
        f"/sales/{authorized_user_client_cre_bus[0].business_id}/{test_create_sale_cli[0].sale_id}"
        
    )
    assert res.status_code == 200
    sale = schemas.SaleResponse(**res.json())
    assert sale.sale_id == test_create_sale_cli[0].sale_id
    
def test_delete_sale(authorized_user_client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = authorized_user_client.delete(
        f"/sales/{authorized_user_client_cre_bus[0].business_id}/{test_create_sale_cli[0].sale_id}"
        
    )
    assert res.status_code == 204
    
def test_delete_sale_unauthorized(client, authorized_user_client_cre_bus, test_create_sale_cli):
    res = client.delete(
        f"/sales/{authorized_user_client_cre_bus[0].business_id}/{test_create_sale_cli[0].sale_id}"
    )
    assert res.status_code == 401
    