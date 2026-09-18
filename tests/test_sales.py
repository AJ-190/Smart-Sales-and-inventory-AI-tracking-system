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


def test_update_sale(authorized_sup_client, test_get_businesses, authorized_sup_products_create):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.post(
        f"/sales/{business_id}",
        json={
            "payment_method": "cash",
            "amount_paid": 4000,
            "list_items": [{"product_id": authorized_sup_products_create[0].product_id, "quantity": 1}]
        }
    )
    assert res.status_code == 201
    sale_id = res.json()["sale_id"]

    res = authorized_sup_client.put(
        f"/sales/{business_id}/{sale_id}",
        json={
            "payment_method": "momo",
            "amount_paid": 8000,
            "list_items": [{"product_id": authorized_sup_products_create[1].product_id, "quantity": 2}]
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sale_id"] == sale_id
    assert data["payment_method"] == "momo"
    assert data["amount_paid"] == 8000
    assert len(data["sales_items"]) == 1
    assert data["sales_items"][0]["product_id"] == authorized_sup_products_create[1].product_id


def test_update_sale_not_found(authorized_sup_client, test_get_businesses):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.put(
        f"/sales/{business_id}/99999",
        json={"payment_method": "momo"}
    )
    assert res.status_code == 404


def test_update_sale_insufficient_stock(authorized_sup_client, test_get_businesses, authorized_sup_products_create):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.post(
        f"/sales/{business_id}",
        json={
            "payment_method": "cash",
            "amount_paid": 4000,
            "list_items": [{"product_id": authorized_sup_products_create[0].product_id, "quantity": 1}]
        }
    )
    assert res.status_code == 201
    sale_id = res.json()["sale_id"]

    res = authorized_sup_client.put(
        f"/sales/{business_id}/{sale_id}",
        json={
            "payment_method": "momo",
            "amount_paid": 8000,
            "list_items": [{"product_id": authorized_sup_products_create[1].product_id, "quantity": 10000}]
        }
    )
    assert res.status_code == 400


def test_update_sale_forbidden(authorized_user_client, authorized_sup_client, test_get_businesses, authorized_sup_products_create):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.post(
        f"/sales/{business_id}",
        json={
            "payment_method": "cash",
            "amount_paid": 4000,
            "list_items": [{"product_id": authorized_sup_products_create[0].product_id, "quantity": 1}]
        }
    )
    assert res.status_code == 201
    sale_id = res.json()["sale_id"]

    res = authorized_user_client.put(
        f"/sales/{business_id}/{sale_id}",
        json={"payment_method": "momo"}
    )
    assert res.status_code == 403


def test_receipt(authorized_sup_client, test_get_businesses, authorized_sup_products_create):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.post(
        f"/sales/{business_id}",
        json={
            "payment_method": "cash",
            "amount_paid": 4000,
            "list_items": [{"product_id": authorized_sup_products_create[0].product_id, "quantity": 1}]
        }
    )
    assert res.status_code == 201
    sale_id = res.json()["sale_id"]

    res = authorized_sup_client.get(f"/sales/{business_id}/{sale_id}/receipt")
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["sale_id"] == sale_id
    assert "business" in receipt
    assert "items" in receipt
    assert "total" in receipt


def test_receipt_unauthorized(client, test_get_businesses, authorized_sup_products_create):
    business_id = test_get_businesses[0].business.business_id
    res = client.get(f"/sales/{business_id}/1/receipt")
    assert res.status_code == 401


def test_receipt_not_found(authorized_sup_client, test_get_businesses):
    business_id = test_get_businesses[0].business.business_id
    res = authorized_sup_client.get(f"/sales/{business_id}/99999/receipt")
    assert res.status_code == 404
    