import pytest
from src.businesses import schemas


def test_business_create(authorized_sup_client, test_user):
    res = authorized_sup_client.post(
        "/businesses/create", json={"name":"Core.AI"})
    
    
    assert res.status_code == 201
    business = schemas.BusinessReposnse(**res.json())
    assert business.name == "Core.AI"
    assert business.business_id is not None
    assert business.is_active
    
def test_business_dup_emails(authorized_sup_client, test_business):
    res = authorized_sup_client.post(
        "/businesses/create",
        json={"name": "Core.AI"}
    )
    assert res.status_code == 409

# def test_get_businesses(authorized_sup_client,test_get_businesses ):
    
    
def test_business_by_id(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.get(
        f"/businesses/{test_get_businesses[0].business.business_id}"
    )
    assert res.status_code == 200

    business = schemas.BusinessWithMemberCount(**res.json())
    assert business.business.business_id == test_get_businesses[0].business.business_id
    
    
def get_business_not_exist(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.get(
        "/businesses/34"
    )
    assert res.status_code == 404
    

def test_update_business(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.put(
        f"/businesses/{test_get_businesses[0].business.business_id}",
        json={"name": "Great Addy"}
    )
    
    assert res.status_code == 200
    business = schemas.BusinessReposnse(**res.json())
    assert business.name == "Great Addy"
    
def update_business_unauthorized(authorized_user_client, test_get_businesses):
    res = authorized_user_client.put(
        f"/businesses/{test_get_businesses[0].business.business_id}",
        json={"name": "Great Addy"}
    )
    
    assert res.status_code == 403
    
def test_delete_business(authorized_sup_client,test_get_businesses):
    res = authorized_sup_client.delete(
        f"/businesses/{test_get_businesses[0].business.business_id}"
    )
    assert res.status_code == 204
    
def test_del_business_unauthorized(client, test_get_businesses):
    res = client.delete(
        f"/businesses/{test_get_businesses[0].business.business_id}"
    )

    assert res.status_code == 401
    
def get_business_unauthorized(authorized_user_client,test_get_businesses ):
    res = authorized_user_client.get(
        f"/businesses/"
    )
    
    assert res.status_code == 404
    
def test_get_business_key(authorized_sup_client, test_get_businesses):
    res = authorized_sup_client.get(
        f"/businesses/business_key/{test_get_businesses[0].business.business_id}"
    )
    
    assert res.status_code == 200
    key = schemas.Business_key(**res.json())
    print(key.business_key)
    