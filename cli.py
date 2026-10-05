"""Command-line interface for the inventory API.

  python cli.py            friendly interactive menu (starts the server for you)
  python cli.py list       one-shot commands, e.g.:
  python cli.py add --name "Milk" --price 1.5 --quantity 10
  python cli.py import --barcode 3017620422003 --quantity 5
"""
import argparse
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests

try:  # makes the arrow keys work at prompts on Linux/macOS
    import readline  # noqa: F401
except ImportError:
    pass

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")
SERVER_HINT = "Is the server running? Start it with: python app.py"


# ---------------------------------------------------------------------------
# One-shot commands (flags)
# ---------------------------------------------------------------------------
def call(method, path, **kwargs):
    try:
        resp = requests.request(method, API_URL + path, timeout=15, **kwargs)
    except requests.RequestException:
        print(f"Could not reach API at {API_URL}. {SERVER_HINT}")
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
# Server helpers (the menu starts the API for you if it is not running)
# ---------------------------------------------------------------------------
def server_is_up():
    try:
        requests.get(API_URL + "/", timeout=2)
        return True
    except requests.RequestException:
        return False


def start_local_server():
    """Start app.py in the background. Returns the process, or None on failure."""
    parsed = urlparse(API_URL)
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        return None
    port = parsed.port or 5000
    here = os.path.dirname(os.path.abspath(__file__))
    code = f"from app import create_app; create_app().run(port={port})"
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=here,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if server_is_up():
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    proc.terminate()
    return None


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------
MENU = """
========================================
   INVENTORY MANAGER
========================================
  1) Show my inventory
  2) View one item
  3) Add an item
  4) Change an item
  5) Remove an item
  6) Find a product by barcode   (OpenFoodFacts)
  7) Search products by name     (OpenFoodFacts)
  0) Quit
"""


def _request(method, path, **kwargs):
    """Return (status_code, data). status_code is None if the API is unreachable."""
    try:
        resp = requests.request(method, API_URL + path, timeout=15, **kwargs)
    except requests.RequestException:
        return None, f"Could not reach API at {API_URL}. {SERVER_HINT}"
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, resp.text


def _ok(status, data):
    """Print a friendly error and return False if the request failed."""
    if status is None:
        print(f"  {data}")
        return False
    if status >= 400:
        message = data.get("error", data) if isinstance(data, dict) else data
        print(f"  Sorry, that did not work ({status}): {message}")
        return False
    return True


def _ask(prompt, cast=str, required=True):
    while True:
        raw = input(prompt).strip()
        if not raw:
            if not required:
                return None
            print("  Please type something (or press Ctrl+C to quit).")
            continue
        try:
            return cast(raw)
        except ValueError:
            print("  That does not look right, please try again.")


def _confirm(prompt):
    return input(prompt).strip().lower() in ("y", "yes")


def _clip(text, width):
    text = str(text or "-")
    return text if len(text) <= width else text[:width - 1] + "~"


def _print_table(items):
    print(f"  {'ID':<4}{'Name':<28}{'Brand':<20}{'Price':>8}{'Qty':>6}")
    print("  " + "-" * 66)
    for item in items:
        price = float(item.get("price") or 0)
        print(f"  {str(item.get('id')):<4}{_clip(item.get('name'), 26):<28}"
              f"{_clip(item.get('brand'), 18):<20}{price:>8.2f}{item.get('quantity') or 0:>6}")


def _print_product(product):
    ingredients = _clip(product.get("ingredients"), 90)
    print(f"  {product.get('name')}  |  brand: {product.get('brand') or '-'}"
          f"  |  barcode: {product.get('barcode') or '-'}")
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


def _show_inventory():
    """Print the inventory table. Returns the list of items, or None on error."""
    status, data = _request("GET", "/inventory")
    if not _ok(status, data):
        return None
    if not data:
        print("  Your inventory is empty. Use option 3, 6 or 7 to add products.")
        return data
    _print_table(data)
    return data


def _menu_list():
    _show_inventory()


def _menu_view():
    if not _show_inventory():
        return
    item_id = _ask("Item ID to view (blank to go back): ", int, required=False)
    if item_id is None:
        return
    status, data = _request("GET", f"/inventory/{item_id}")
    if _ok(status, data):
        _print_table([data])
        print(f"    ingredients: {_clip(data.get('ingredients'), 90)}")


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
        print("  Added:")
        _print_table([data])


def _menu_update():
    if not _show_inventory():
        return
    item_id = _ask("Item ID to change (blank to go back): ", int, required=False)
    if item_id is None:
        return
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
        print("  Nothing to change.")
        return
    status, data = _request("PATCH", f"/inventory/{item_id}", json=body)
    if _ok(status, data):
        print("  Updated:")
        _print_table([data])


def _menu_delete():
    if not _show_inventory():
        return
    item_id = _ask("Item ID to remove (blank to go back): ", int, required=False)
    if item_id is None:
        return
    if not _confirm(f"  Really remove item {item_id}? (y/n): "):
        print("  Cancelled.")
        return
    status, data = _request("DELETE", f"/inventory/{item_id}")
    if _ok(status, data):
        print("  Removed.")


def _menu_lookup():
    barcode = _ask("Barcode (for example 3017620422003): ")
    print("  Looking it up on OpenFoodFacts...")
    status, data = _request("GET", f"/external/barcode/{barcode}")
    if not _ok(status, data):
        return
    _print_product(data)
    if _confirm("  Add this product to your inventory? (y/n): "):
        body = {"barcode": barcode}
        body.update(_price_and_quantity())
        status, data = _request("POST", "/inventory/import", json=body)
        if _ok(status, data):
            print("  Added:")
            _print_table([data])


def _menu_search():
    name = _ask("Product name to search for: ")
    print("  Searching OpenFoodFacts...")
    status, data = _request("GET", "/external/search", params={"name": name})
    if not _ok(status, data):
        return
    if not data:
        print("  No products found.")
        return
    for number, product in enumerate(data, start=1):
        print(f" {number}.")
        _print_product(product)
    choice = _ask("Pick a number to add to your inventory (blank to cancel): ", int, required=False)
    if choice is None:
        return
    if not 1 <= choice <= len(data):
        print("  That number is not in the list.")
        return
    product = data[choice - 1]
    body = {k: product[k] for k in ("name", "brand", "barcode", "ingredients") if product.get(k)}
    body.update(_price_and_quantity())
    status, data = _request("POST", "/inventory", json=body)
    if _ok(status, data):
        print("  Added:")
        _print_table([data])


def _menu_loop():
    actions = {"1": _menu_list, "2": _menu_view, "3": _menu_add, "4": _menu_update,
               "5": _menu_delete, "6": _menu_lookup, "7": _menu_search}
    while True:
        print(MENU)
        try:
            choice = input("Choose an option (0-7): ").strip()
            if choice == "0":
                print("Goodbye!")
                return 0
            action = actions.get(choice)
            if action is None:
                print("  Invalid choice, please enter a number from the menu.")
                continue
            action()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return 0


def interactive():
    server = None
    if not server_is_up():
        print("Starting the inventory server...")
        server = start_local_server()
        if server is None:
            print(f"Could not start the server. {SERVER_HINT}")
            return 1
        print("Server ready. (Your inventory is kept in memory and resets when you quit.)")
    try:
        return _menu_loop()
    finally:
        if server is not None:
            server.terminate()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return interactive()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
