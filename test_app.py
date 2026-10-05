from unittest.mock import patch

import pytest
import requests

from app import create_app

FAKE_PRODUCT = {"name": "Nutella", "brand": "Ferrero", "barcode": "3017620422003",
                "ingredients": "Sugar, palm oil"}


@pytest.fixture
def client():
    return create_app().test_client()


def make(client, **kw):
    body = {"name": "Milk", "price": 1.5, "quantity": 10}
    body.update(kw)
    return client.post("/inventory", json=body)


# ---- Root ----
def test_index(client):
    assert client.get("/").status_code == 200

# ---- Create ----
def test_create_item(client):
    r = make(client)
    assert r.status_code == 201
    assert r.json["id"] == 1 and r.json["name"] == "Milk"

def test_create_requires_name(client):
    assert client.post("/inventory", json={"price": 2}).status_code == 400

def test_create_rejects_bad_price(client):
    assert make(client, price=-1).status_code == 400
    assert make(client, price="abc").status_code == 400

def test_create_rejects_bad_quantity(client):
    assert make(client, quantity=1.5).status_code == 400

def test_create_rejects_non_json(client):
    assert client.post("/inventory", data="nope").status_code == 400

# ---- Read ----
def test_list_empty(client):
    r = client.get("/inventory")
    assert r.status_code == 200 and r.json == []

def test_list_and_filter(client):
    make(client, name="Milk"); make(client, name="Bread")
    assert len(client.get("/inventory").json) == 2
    assert len(client.get("/inventory?name=bre").json) == 1

def test_get_item(client):
    make(client)
    assert client.get("/inventory/1").json["name"] == "Milk"

def test_get_missing(client):
    assert client.get("/inventory/99").status_code == 404

# ---- Update ----
def test_patch_item(client):
    make(client)
    r = client.patch("/inventory/1", json={"quantity": 3})
    assert r.status_code == 200
    assert r.json["quantity"] == 3 and r.json["name"] == "Milk"

def test_patch_missing(client):
    assert client.patch("/inventory/5", json={"quantity": 1}).status_code == 404

def test_patch_invalid(client):
    make(client)
    assert client.patch("/inventory/1", json={"price": -5}).status_code == 400

# ---- Delete ----
def test_delete_item(client):
    make(client)
    assert client.delete("/inventory/1").status_code == 200
    assert client.get("/inventory/1").status_code == 404

def test_delete_missing(client):
    assert client.delete("/inventory/1").status_code == 404

# ---- External API (mocked) ----
@patch("external_api.fetch_by_barcode", return_value=FAKE_PRODUCT.copy())
def test_external_barcode(mock_fetch, client):
    r = client.get("/external/barcode/3017620422003")
    assert r.status_code == 200 and r.json["name"] == "Nutella"

@patch("external_api.fetch_by_barcode", return_value=None)
def test_external_barcode_not_found(mock_fetch, client):
    assert client.get("/external/barcode/000").status_code == 404

@patch("external_api.fetch_by_barcode", side_effect=requests.ConnectionError("down"))
def test_external_barcode_api_down(mock_fetch, client):
    assert client.get("/external/barcode/123").status_code == 502

@patch("external_api.search_by_name", return_value=[FAKE_PRODUCT.copy()])
def test_external_search(mock_search, client):
    r = client.get("/external/search?name=nutella")
    assert r.status_code == 200 and len(r.json) == 1

def test_external_search_requires_name(client):
    assert client.get("/external/search").status_code == 400

@patch("external_api.fetch_by_barcode", return_value=FAKE_PRODUCT.copy())
def test_import_by_barcode(mock_fetch, client):
    r = client.post("/inventory/import", json={"barcode": "3017620422003", "quantity": 7, "price": 4.2})
    assert r.status_code == 201
    assert r.json["name"] == "Nutella" and r.json["quantity"] == 7
    assert len(client.get("/inventory").json) == 1

@patch("external_api.search_by_name", return_value=[FAKE_PRODUCT.copy()])
def test_import_by_name(mock_search, client):
    r = client.post("/inventory/import", json={"name": "nutella"})
    assert r.status_code == 201 and r.json["brand"] == "Ferrero"

@patch("external_api.search_by_name", return_value=[])
def test_import_name_not_found(mock_search, client):
    assert client.post("/inventory/import", json={"name": "zzz"}).status_code == 404

def test_import_requires_identifier(client):
    assert client.post("/inventory/import", json={}).status_code == 400
