def test_get_debts(client):
    res = client.get("/debts/")
    assert res.status_code == 401
