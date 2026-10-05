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


# ---- Interactive menu ----
import pytest  # noqa: E402
import requests  # noqa: E402


@pytest.fixture(autouse=True)
def _server_up(monkeypatch):
    """Pretend the API is already running so tests never start a real server."""
    monkeypatch.setattr(cli, "server_is_up", lambda: True)


def resp(status, payload):
    m = MagicMock(status_code=status, ok=status < 400)
    m.json.return_value = payload
    return m


@patch("cli.requests.request")
@patch("builtins.input", side_effect=["1", "0"])
def test_interactive_list(mock_input, mock_req, capsys):
    mock_req.return_value = resp(200, [{"id": 1, "name": "Milk", "price": 1.5, "quantity": 3}])
    assert cli.main([]) == 0
    assert "Milk" in capsys.readouterr().out


@patch("builtins.input", side_effect=["9", "0"])
def test_interactive_invalid_choice(mock_input, capsys):
    assert cli.main([]) == 0
    assert "Invalid choice" in capsys.readouterr().out


@patch("cli.requests.request")
@patch("builtins.input", side_effect=["3", "Milk", "", "", "1.5", "4", "0"])
def test_interactive_add(mock_input, mock_req):
    mock_req.return_value = resp(201, {"id": 1, "name": "Milk"})
    cli.main([])
    assert mock_req.call_args[1]["json"] == {"name": "Milk", "price": 1.5, "quantity": 4}


@patch("cli.requests.request")
@patch("builtins.input", side_effect=["7", "nutella", "1", "4.99", "5", "0"])
def test_interactive_search_and_add(mock_input, mock_req):
    product = {"name": "Nutella", "brand": "Ferrero", "barcode": "3017620422003", "ingredients": "Sugar"}
    mock_req.side_effect = [resp(200, [product]), resp(201, {"id": 1, "name": "Nutella"})]
    cli.main([])
    body = mock_req.call_args_list[1][1]["json"]
    assert body["name"] == "Nutella" and body["barcode"] == "3017620422003"
    assert body["price"] == 4.99 and body["quantity"] == 5


@patch("cli.requests.request")
@patch("builtins.input", side_effect=["6", "123", "n", "0"])
def test_interactive_lookup_decline(mock_input, mock_req):
    mock_req.return_value = resp(200, {"name": "Nutella", "brand": "Ferrero", "barcode": "123"})
    cli.main([])
    assert mock_req.call_count == 1


@patch("cli.requests.request", side_effect=requests.ConnectionError("down"))
@patch("builtins.input", side_effect=["1", "0"])
def test_interactive_api_down(mock_input, mock_req, capsys):
    assert cli.main([]) == 0
    assert "Could not reach API" in capsys.readouterr().out


@patch("cli.requests.request")
@patch("builtins.input", side_effect=["5", "", "0"])
def test_interactive_delete_can_go_back(mock_input, mock_req):
    mock_req.return_value = resp(200, [{"id": 1, "name": "Milk", "price": 1.5, "quantity": 3}])
    cli.main([])
    assert mock_req.call_count == 1  # only the list was fetched, nothing deleted


@patch("builtins.input", side_effect=["0"])
def test_interactive_autostarts_server(mock_input, monkeypatch):
    server = MagicMock()
    monkeypatch.setattr(cli, "server_is_up", lambda: False)
    monkeypatch.setattr(cli, "start_local_server", lambda: server)
    assert cli.main([]) == 0
    server.terminate.assert_called_once()


@patch("builtins.input", side_effect=["0"])
def test_interactive_server_fails_to_start(mock_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "server_is_up", lambda: False)
    monkeypatch.setattr(cli, "start_local_server", lambda: None)
    assert cli.main([]) == 1
    assert "Could not start the server" in capsys.readouterr().out
