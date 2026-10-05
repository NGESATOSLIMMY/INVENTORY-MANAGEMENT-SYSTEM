from unittest.mock import patch, MagicMock

import cli


def ok_response():
    m = MagicMock(ok=True)
    m.json.return_value = {"id": 1}
    return m


@patch("cli.requests.request")
def test_list(mock_req):
    mock_req.return_value = ok_response()
    assert cli.main(["list"]) == 0
    assert mock_req.call_args[0][:2] == ("GET", cli.API_URL + "/inventory")


@patch("cli.requests.request")
def test_add_sends_fields(mock_req):
    mock_req.return_value = ok_response()
    cli.main(["add", "--name", "Milk", "--price", "1.5", "--quantity", "4"])
    assert mock_req.call_args[1]["json"] == {"name": "Milk", "price": 1.5, "quantity": 4}


@patch("cli.requests.request")
def test_update_uses_patch(mock_req):
    mock_req.return_value = ok_response()
    cli.main(["update", "3", "--quantity", "9"])
    assert mock_req.call_args[0][0] == "PATCH"
    assert mock_req.call_args[0][1].endswith("/inventory/3")


@patch("cli.requests.request")
def test_delete(mock_req):
    mock_req.return_value = ok_response()
    cli.main(["delete", "2"])
    assert mock_req.call_args[0][0] == "DELETE"


@patch("cli.requests.request")
def test_import_barcode(mock_req):
    mock_req.return_value = ok_response()
    cli.main(["import", "--barcode", "123", "--quantity", "5"])
    assert mock_req.call_args[1]["json"] == {"barcode": "123", "quantity": 5}


def test_import_requires_identifier():
    assert cli.main(["import"]) == 1
