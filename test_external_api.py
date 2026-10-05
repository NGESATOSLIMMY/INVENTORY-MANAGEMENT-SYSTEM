from unittest.mock import patch, MagicMock

import external_api


def mock_response(payload, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


@patch("external_api.requests.get")
def test_fetch_by_barcode_found(mock_get):
    mock_get.return_value = mock_response(
        {"status": 1, "product": {"product_name": "Nutella", "brands": "Ferrero",
                                  "ingredients_text": "Sugar"}})
    result = external_api.fetch_by_barcode("123")
    assert result["name"] == "Nutella" and result["barcode"] == "123"


@patch("external_api.requests.get")
def test_fetch_by_barcode_missing(mock_get):
    mock_get.return_value = mock_response({"status": 0})
    assert external_api.fetch_by_barcode("000") is None


@patch("external_api.requests.get")
def test_fetch_by_barcode_404(mock_get):
    mock_get.return_value = mock_response({}, status_code=404)
    assert external_api.fetch_by_barcode("000") is None


@patch("external_api.requests.get")
def test_search_by_name(mock_get):
    mock_get.return_value = mock_response(
        {"products": [{"product_name": "A", "code": "1"}, {"product_name": "B", "code": "2"}]})
    results = external_api.search_by_name("x")
    assert [r["name"] for r in results] == ["A", "B"]
