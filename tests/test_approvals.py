import pytest
from src.businesses import schemas, models as bm


def test_send_approval(authorized_user_client,test_get_businesses, test_get_business_key):
    
    res = authorized_user_client.post(
        f"/businesses/approvals/send_approval/",
        json={"business_key": test_get_business_key,
              "reason": "I wanna be cashier",
              "role": "cashier"}
    )

    assert res.status_code == 201
    approval = schemas.ApprovalsResponseUser(**res.json())
    assert approval.business_id == test_get_businesses[0].business.business_id
    assert approval.status == bm.ApprovalStatus.pending

def test_send_approval_invalid_business_key(authorized_user_client, test_get_businesses):
    res = authorized_user_client.post(
        f"/businesses/approvals/send_approval/",
        json={"business_key": "HSSHSHSHS",
              "reason": "I wanna be cashier",
              "role": "cashier"
              }
        )
    assert res.status_code == 404
    

def test_send_approval_unauthenticated(client, test_get_business_key):
    res = client.post(
        f"/businesses/approvals/send_approval",
        json={"business_key": test_get_business_key,
              "reason": "I want be manager",
              "role": "manager"}
    )
    
    assert res.status_code == 401
    
    
def test_get_approvals(authorized_sup_client, test_get_businesses, test_send_approval):
    res = authorized_sup_client.get(
        f"/businesses/approvals/get_approvals/{test_get_businesses[0].business.business_id}?status=pending"
    )
    
    assert res.status_code == 200
    approval = [schemas.ApprovalsResponse(**approval) for approval in res.json()]
    assert approval[0].business_id == test_send_approval.business_id
    
    
def test_get_approvals_unauthorized(client, test_get_businesses,test_send_approval):
    res = client.get(
        f"/businesses/approvals/get_approvals/{test_get_businesses[0].business.business_id}?status=pending"
    )
    assert res.status_code == 401
    
    
def test_get_approvals_unauthorized_cross( authorized_user_client,test_get_businesses, test_send_approval, authorized_user_client_test_businesses):
    res = authorized_user_client.get(
        f"/businesses/approvals/get_approvals/{test_get_businesses[0].business.business_id}?status=pending"
    )
    assert res.status_code == 404
    

def test_reject_approval(authorized_sup_client, test_get_businesses, test_send_approval):
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id":test_send_approval.approval_id, "dir":0 }
    )
    
    assert res.status_code == 200
    approval = schemas.ApprovalsResponse(**res.json())
    assert approval.approval_id == test_send_approval.approval_id
    assert approval.status == bm.ApprovalStatus.rejected
    
def test_reject_approval_unauthorized(authorized_user_client,test_get_businesses, test_send_approval, authorized_user_client_test_businesses):
    res = authorized_user_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id":test_send_approval.approval_id, "dir":0 }
    )
    assert res.status_code == 404
    
 
def test_reject_already_rejected(authorized_sup_client,test_get_businesses,test_send_approval):
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 0}
    )
    
    assert res.status_code == 200
    
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 0}
    )
    assert res.status_code == 409
    
    

def test_approved_approval(authorized_sup_client, test_get_businesses, test_send_approval):
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id":test_send_approval.approval_id, "dir":1 }
    )
    
    assert res.status_code == 200
    approval = schemas.ApprovalsResponse(**res.json())
    assert approval.approval_id == test_send_approval.approval_id
    assert approval.status == bm.ApprovalStatus.approved
    
    
def test_approved_approval_unauthorized(authorized_user_client,test_get_businesses, test_send_approval, authorized_user_client_test_businesses):
    res = authorized_user_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id":test_send_approval.approval_id, "dir":1 }
    )
    assert res.status_code == 404
    
    
    

def test_approved_already_rejected(authorized_sup_client,test_get_businesses,test_send_approval):
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 1}
    )
    
    assert res.status_code == 200
    
    res = authorized_sup_client.post(
        f"/businesses/approvals/confirm_approvals/{test_get_businesses[0].business.business_id}",
        json={"approval_id": test_send_approval.approval_id, "dir": 1}
    )
    assert res.status_code == 409