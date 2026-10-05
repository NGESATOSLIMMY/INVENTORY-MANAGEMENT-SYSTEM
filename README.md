# Inventory Management System (Flask REST API + CLI)

An administrator portal backend for a retail company. Employees can add, view, edit and delete
inventory items, and pull product details from the OpenFoodFacts API (https://world.openfoodfacts.org/data)
by barcode or name.

## Files
- `app.py` - Flask REST API (CRUD + external helper routes)
- `external_api.py` - OpenFoodFacts wrapper
- `cli.py` - command-line interface that talks to the API
- `test_app.py`, `test_external_api.py`, `test_cli.py` - pytest suite (all network calls mocked)

Data is stored in an in-memory list (resets when the server restarts).

## Setup
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python app.py        # serves http://127.0.0.1:5000

## API endpoints
- GET    /inventory                     list items (optional ?name= filter)
- GET    /inventory/<id>                get one item
- POST   /inventory                     create item (name required)
- PATCH  /inventory/<id>                partially update an item
- DELETE /inventory/<id>                delete an item
- GET    /external/barcode/<barcode>    look up a product on OpenFoodFacts (not saved)
- GET    /external/search?name=         search OpenFoodFacts by name (not saved)
- POST   /inventory/import              fetch by barcode or name and add to inventory

Errors return JSON {"error": "..."} with 400 (bad input), 404 (not found) or 502 (external API failure).

## CLI usage (server must be running)
    python cli.py add --name "Milk" --price 1.5 --quantity 10
    python cli.py list
    python cli.py get 1
    python cli.py update 1 --quantity 8
    python cli.py delete 1
    python cli.py lookup 3017620422003
    python cli.py search "nutella"
    python cli.py import --barcode 3017620422003 --quantity 5 --price 4.99
    python cli.py import --name "nutella"

Set INVENTORY_API_URL to point the CLI at a different host.

## External API
Uses OpenFoodFacts (no API key required) with a custom User-Agent, as their docs request.
Rate limits: 15 product reads/min and 10 searches/min per IP.

## Tests
    pytest -v

External HTTP calls are mocked with unittest.mock, so tests run offline.

## Git workflow used
Feature branches (feature/crud-routes, feature/external-api, feature/cli, feature/tests),
each merged into main through a pull request and deleted after merging.

## Interactive menu
Run the CLI with no arguments to open a menu-driven interface:

    python cli.py

From the menu you can list, view, add, update and delete items, look up a product by barcode,
or search OpenFoodFacts by name and add a result straight into the inventory.
The one-shot commands above still work for scripting.
