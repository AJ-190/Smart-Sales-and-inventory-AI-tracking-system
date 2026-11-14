from unittest.mock import patch

import httpx

from src.products import schemas


class _FakeAsyncClient:
    def __init__(self, response=None, error=None, **kwargs):
        self._response = response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


def _http_response(status_code=200, payload=None, content=None):
    request = httpx.Request("GET", "https://example.test/product")
    if content is not None:
        return httpx.Response(status_code, content=content, request=request)
    return httpx.Response(status_code, json=payload, request=request)


def _mock_external(response=None, error=None):
    return patch(
        "src.products.service.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response=response, error=error),
    )


def _product(name, barcode=None, price=10.0):
    data = {
        "name": name,
        "price": price,
        "cost_price": 5.0,
        "quantity": 3,
    }
    if barcode is not None:
        data["barcode"] = barcode
    return data


def test_create_and_scan_local_barcode(authorized_user_client, authorized_user_client_test_businesses):
    business_id = authorized_user_client_test_businesses[0].business_id
    barcode = "0123456789012"

    res = authorized_user_client.post(
        f"/products/{business_id}",
        json=_product("Barcoded product", barcode=barcode),
    )

    assert res.status_code == 201
    created = schemas.ProductResponse(**res.json())
    assert created.barcode == barcode

    scan = authorized_user_client.get(f"/products/{business_id}/scan/{barcode}")

    assert scan.status_code == 200
    body = scan.json()
    assert body["found_locally"] is True
    assert body["source"] == "inventory"
    assert body["suggested_name"] is None
    assert body["product"]["product_id"] == created.product_id
    assert body["product"]["barcode"] == barcode


def test_scan_alphanumeric_code128_barcode(authorized_user_client, authorized_user_client_test_businesses):
    business_id = authorized_user_client_test_businesses[0].business_id
    barcode = "CODE128-0001234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"

    create = authorized_user_client.post(
        f"/products/{business_id}",
        json=_product("Long code product", barcode=barcode),
    )
    assert create.status_code == 201

    scan = authorized_user_client.get(f"/products/{business_id}/scan/{barcode}")
    assert scan.status_code == 200
    assert scan.json()["product"]["barcode"] == barcode


def test_scan_unknown_barcode_returns_external_suggestion(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id
    response = _http_response(payload={"status": 1, "product": {"product_name": "Nutella"}})

    with _mock_external(response=response):
        scan = authorized_user_client.get(f"/products/{business_id}/scan/9999999999999")

    assert scan.status_code == 200
    body = scan.json()
    assert body["found_locally"] is False
    assert body["source"] == "openfoodfacts"
    assert body["product"] is None
    assert body["suggested_name"] == "Nutella"


def test_scan_unknown_barcode_and_upstream_404(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    with _mock_external(response=_http_response(status_code=404, content=b"{}")):
        scan = authorized_user_client.get(f"/products/{business_id}/scan/0000000000000")

    assert scan.status_code == 404


def test_scan_upstream_status_zero_is_not_found(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    with _mock_external(response=_http_response(payload={"status": 0})):
        scan = authorized_user_client.get(f"/products/{business_id}/scan/1111111111111")

    assert scan.status_code == 404


def test_scan_upstream_http_error_returns_502(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    with _mock_external(response=_http_response(status_code=500, content=b"{}")):
        scan = authorized_user_client.get(f"/products/{business_id}/scan/2222222222222")

    assert scan.status_code == 502


def test_scan_upstream_connection_error_returns_503(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    with _mock_external(error=httpx.ConnectError("boom")):
        scan = authorized_user_client.get(f"/products/{business_id}/scan/3333333333333")

    assert scan.status_code == 503


def test_duplicate_barcode_same_business_conflicts(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id
    barcode = "1234567890128"

    first = authorized_user_client.post(
        f"/products/{business_id}",
        json=_product("First barcode product", barcode=barcode),
    )
    assert first.status_code == 201

    duplicate = authorized_user_client.post(
        f"/products/{business_id}",
        json=_product("Second barcode product", barcode=barcode),
    )
    assert duplicate.status_code == 409


def test_same_barcode_allowed_in_different_businesses(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_one = authorized_user_client_test_businesses[0].business_id
    business_two = authorized_user_client_test_businesses[1].business_id
    barcode = "4006381333931"

    first = authorized_user_client.post(
        f"/products/{business_one}",
        json=_product("Business one product", barcode=barcode),
    )
    assert first.status_code == 201

    second = authorized_user_client.post(
        f"/products/{business_two}",
        json=_product("Business two product", barcode=barcode),
    )
    assert second.status_code == 201

    scan = authorized_user_client.get(f"/products/{business_two}/scan/{barcode}")
    assert scan.status_code == 200
    assert scan.json()["product"]["name"] == "Business two product"


def test_update_product_barcode_is_normalized(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    create = authorized_user_client.post(
        f"/products/{business_id}",
        json=_product("Needs barcode product"),
    )
    assert create.status_code == 201
    product_id = create.json()["product_id"]

    update = authorized_user_client.put(
        f"/products/{business_id}/{product_id}",
        json={"barcode": "  4006381333931  "},
    )
    assert update.status_code == 200
    assert update.json()["barcode"] == "4006381333931"

    scan = authorized_user_client.get(f"/products/{business_id}/scan/4006381333931")
    assert scan.status_code == 200
    assert scan.json()["found_locally"] is True


def test_scan_empty_barcode_returns_422(
    authorized_user_client, authorized_user_client_test_businesses
):
    business_id = authorized_user_client_test_businesses[0].business_id

    scan = authorized_user_client.get(f"/products/{business_id}/scan/%20")

    assert scan.status_code == 422


def test_scan_requires_business_membership(authorized_user_client, test_get_businesses):
    other_business_id = test_get_businesses[0].business.business_id

    scan = authorized_user_client.get(f"/products/{other_business_id}/scan/1234567890128")

    assert scan.status_code == 403
