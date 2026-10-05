"""Command-line interface for the inventory API.

Start the server first (python app.py), then e.g.:
    python cli.py list
    python cli.py add --name "Milk" --price 1.5 --quantity 10
    python cli.py import --barcode 3017620422003 --quantity 5
"""
import argparse
import json
import os
import sys

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")


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
    p = argparse.ArgumentParser(description="Inventory management CLI")
    sub = p.add_subparsers(dest="command", required=True)

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


def main(argv=None):
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
