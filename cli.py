"""Command-line interface for the inventory API.

Start the server first (python app.py), then either:

  Interactive menu:   python cli.py
  Single commands:    python cli.py list
                      python cli.py add --name "Milk" --price 1.5 --quantity 10
                      python cli.py import --barcode 3017620422003 --quantity 5
"""
import argparse
import json
import os
import sys

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")


# ---------------------------------------------------------------------------
# One-shot commands (flags)
# ---------------------------------------------------------------------------
def call(method, path, **kwargs):
    try:
        resp = requests.request(method, API_URL + path, timeout=15, **kwargs)
    except requests.RequestException as exc:
        print(f"Could not reach API at {API_URL}: {exc}")
        return 1
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    return 0 if resp.ok else 1


def build_parser():
    p = argparse.ArgumentParser(description="Inventory management CLI "
                                            "(run with no arguments for the interactive menu)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("interactive", help="Open the interactive menu")

    s = sub.add_parser("list", help="List all items")
    s.add_argument("--name", help="Filter by name")

    s = sub.add_parser("get", help="Get one item")
    s.add_argument("id", type=int)

    for cmd in ("add", "update"):
        s = sub.add_parser(cmd, help=f"{cmd.capitalize()} an item")
        if cmd == "update":
            s.add_argument("id", type=int)
        s.add_argument("--name", required=(cmd == "add"))
        s.add_argument("--brand")
        s.add_argument("--barcode")
        s.add_argument("--price", type=float)
        s.add_argument("--quantity", type=int)
        s.add_argument("--ingredients")

    s = sub.add_parser("delete", help="Delete an item")
    s.add_argument("id", type=int)

    s = sub.add_parser("lookup", help="Look up a product by barcode (no save)")
    s.add_argument("barcode")

    s = sub.add_parser("search", help="Search OpenFoodFacts by name (no save)")
    s.add_argument("name")

    s = sub.add_parser("import", help="Fetch from OpenFoodFacts and add to inventory")
    s.add_argument("--barcode")
    s.add_argument("--name")
    s.add_argument("--price", type=float)
    s.add_argument("--quantity", type=int)
    return p


def run(args):
    fields = ("name", "brand", "barcode", "price", "quantity", "ingredients")
    body = {k: getattr(args, k) for k in fields if getattr(args, k, None) is not None}
    c = args.command
    if c == "interactive":
        return interactive()
    if c == "list":
        return call("GET", "/inventory", params={"name": args.name} if args.name else None)
    if c == "get":
        return call("GET", f"/inventory/{args.id}")
    if c == "add":
        return call("POST", "/inventory", json=body)
    if c == "update":
        return call("PATCH", f"/inventory/{args.id}", json=body)
    if c == "delete":
        return call("DELETE", f"/inventory/{args.id}")
    if c == "lookup":
        return call("GET", f"/external/barcode/{args.barcode}")
    if c == "search":
        return call("GET", "/external/search", params={"name": args.name})
    if c == "import":
        if not (args.barcode or args.name):
            print("Provide --barcode or --name")
            return 1
        return call("POST", "/inventory/import", json=body)


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------
MENU = """
==============================
  INVENTORY MANAGEMENT SYSTEM
==============================
  1. List inventory
  2. View an item
  3. Add an item
  4. Update an item
  5. Delete an item
  6. Look up a product by barcode (OpenFoodFacts)
  7. Search OpenFoodFacts by name
  0. Quit
"""


def _request(method, path, **kwargs):
    """Return (status_code, data). status_code is None if the API is unreachable."""
    try:
        resp = requests.request(method, API_URL + path, timeout=15, **kwargs)
    except requests.RequestException as exc:
        return None, f"Could not reach API at {API_URL}: {exc}"
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, resp.text


def _ok(status, data):
    """Print an error and return False if the request failed."""
    if status is None:
        print(f"  {data}")
        return False
    if status >= 400:
        message = data.get("error", data) if isinstance(data, dict) else data
        print(f"  Error ({status}): {message}")
        return False
    return True


def _ask(prompt, cast=str, required=True):
    while True:
        raw = input(prompt).strip()
        if not raw:
            if not required:
                return None
            print("  This field is required.")
            continue
        try:
            return cast(raw)
        except ValueError:
            print("  Invalid value, try again.")


def _confirm(prompt):
    return input(prompt).strip().lower() in ("y", "yes")


def _print_item(item):
    print(f"  [{item.get('id')}] {item.get('name')} | brand: {item.get('brand') or '-'}"
          f" | price: {item.get('price', '-')} | qty: {item.get('quantity', '-')}"
          f" | barcode: {item.get('barcode') or '-'}")


def _print_product(product):
    ingredients = (product.get("ingredients") or "-")[:100]
    print(f"  {product.get('name')} | brand: {product.get('brand') or '-'}"
          f" | barcode: {product.get('barcode') or '-'}")
    print(f"    ingredients: {ingredients}")


def _price_and_quantity():
    body = {}
    price = _ask("Price (optional): ", float, required=False)
    quantity = _ask("Quantity (optional): ", int, required=False)
    if price is not None:
        body["price"] = price
    if quantity is not None:
        body["quantity"] = quantity
    return body


def _menu_list():
    status, data = _request("GET", "/inventory")
    if not _ok(status, data):
        return
    if not data:
        print("  Inventory is empty.")
        return
    for item in data:
        _print_item(item)


def _menu_view():
    item_id = _ask("Item ID: ", int)
    status, data = _request("GET", f"/inventory/{item_id}")
    if _ok(status, data):
        _print_item(data)


def _menu_add():
    body = {"name": _ask("Name: ")}
    brand = _ask("Brand (optional): ", required=False)
    barcode = _ask("Barcode (optional): ", required=False)
    if brand:
        body["brand"] = brand
    if barcode:
        body["barcode"] = barcode
    body.update(_price_and_quantity())
    status, data = _request("POST", "/inventory", json=body)
    if _ok(status, data):
        print("  Item added:")
        _print_item(data)


def _menu_update():
    item_id = _ask("Item ID: ", int)
    print("  Leave a field blank to keep its current value.")
    body = {}
    name = _ask("New name: ", required=False)
    brand = _ask("New brand: ", required=False)
    if name:
        body["name"] = name
    if brand:
        body["brand"] = brand
    body.update(_price_and_quantity())
    if not body:
        print("  Nothing to update.")
        return
    status, data = _request("PATCH", f"/inventory/{item_id}", json=body)
    if _ok(status, data):
        print("  Item updated:")
        _print_item(data)


def _menu_delete():
    item_id = _ask("Item ID: ", int)
    if not _confirm(f"  Delete item {item_id}? (y/n): "):
        print("  Cancelled.")
        return
    status, data = _request("DELETE", f"/inventory/{item_id}")
    if _ok(status, data):
        print("  Item deleted.")


def _menu_lookup():
    barcode = _ask("Barcode: ")
    status, data = _request("GET", f"/external/barcode/{barcode}")
    if not _ok(status, data):
        return
    _print_product(data)
    if _confirm("  Add this product to your inventory? (y/n): "):
        body = {"barcode": barcode}
        body.update(_price_and_quantity())
        status, data = _request("POST", "/inventory/import", json=body)
        if _ok(status, data):
            print("  Added to inventory:")
            _print_item(data)


def _menu_search():
    name = _ask("Product name to search: ")
    status, data = _request("GET", "/external/search", params={"name": name})
    if not _ok(status, data):
        return
    if not data:
        print("  No products found.")
        return
    for number, product in enumerate(data, start=1):
        print(f" {number}.")
        _print_product(product)
    choice = _ask("Pick a number to add to inventory (blank to cancel): ", int, required=False)
    if choice is None:
        return
    if not 1 <= choice <= len(data):
        print("  Invalid number.")
        return
    product = data[choice - 1]
    body = {k: product[k] for k in ("name", "brand", "barcode", "ingredients") if product.get(k)}
    body.update(_price_and_quantity())
    status, data = _request("POST", "/inventory", json=body)
    if _ok(status, data):
        print("  Added to inventory:")
        _print_item(data)


def interactive():
    actions = {"1": _menu_list, "2": _menu_view, "3": _menu_add, "4": _menu_update,
               "5": _menu_delete, "6": _menu_lookup, "7": _menu_search}
    while True:
        print(MENU)
        try:
            choice = input("Choose an option: ").strip()
            if choice == "0":
                print("Goodbye!")
                return 0
            action = actions.get(choice)
            if action is None:
                print("  Invalid choice, try again.")
                continue
            action()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return interactive()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
