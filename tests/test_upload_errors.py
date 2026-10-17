import io
from unittest.mock import patch


def _upload(client, business_id, filename, content):
    return client.post(
        f"/upload/products?business_id={business_id}",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


def test_upload_rejects_unsupported_extension(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    res = _upload(authorized_user_client, bid, "a.txt", b"hello")
    assert res.status_code == 406
    assert res.json()["detail"] == "Only csv and excel is acceptable now"


def test_upload_returns_detail_for_unknown_columns(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    res = _upload(authorized_user_client, bid, "a.csv", b"foo,bar\n1,2\n")
    assert res.status_code == 403
    assert res.json()["detail"] == "Price and product name are required columns"


def test_upload_returns_detail_when_required_columns_missing(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    res = _upload(authorized_user_client, bid, "a.csv", b"sku,category\nA1,Books\n")
    assert res.status_code == 403
    assert res.json()["detail"] == "Price and product name are required columns"


def test_upload_accepts_file_without_quantity_column(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    res = _upload(authorized_user_client, bid, "a.csv", b"name,price\nWidget,10\n")
    assert res.status_code == 201
    assert res.json()["created"] == 1


def test_upload_returns_fallback_message_when_structuring_fails(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    with patch("src.products.service.select", side_effect=RuntimeError("db boom")), patch(
        "src.products.service.structure_products",
        side_effect=RuntimeError("gemini down"),
    ):
        res = _upload(authorized_user_client, bid, "a.csv", b"name,price\nWidget,10\n")
    assert res.status_code == 400
    assert "Could not read the file" in res.json()["detail"]


def test_upload_surfaces_structuring_error_message(
    authorized_user_client, authorized_user_client_test_businesses
):
    bid = authorized_user_client_test_businesses[0].business_id
    with patch("src.products.service.select", side_effect=RuntimeError("db boom")), patch(
        "src.products.service.structure_products",
        return_value="Could not read the prices in that file",
    ):
        res = _upload(authorized_user_client, bid, "a.csv", b"name,price\nWidget,10\n")
    assert res.status_code == 400
    assert res.json()["detail"] == "Could not read the prices in that file"
