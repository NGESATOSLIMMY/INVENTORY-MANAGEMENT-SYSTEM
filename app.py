"""Flask REST API for the inventory management system."""
import requests
from flask import Flask, jsonify, request

import external_api

FIELDS = ("name", "brand", "barcode", "price", "quantity", "ingredients")


def validate(data, partial=False):
    """Return (clean_dict, error_message). Error is None when valid."""
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object"
    clean = {k: data[k] for k in FIELDS if k in data}
    if not partial and not clean.get("name"):
        return None, "'name' is required"
    if "name" in clean and not str(clean["name"]).strip():
        return None, "'name' cannot be empty"
    if "price" in clean:
        if isinstance(clean["price"], bool) or not isinstance(clean["price"], (int, float)) or clean["price"] < 0:
            return None, "'price' must be a non-negative number"
    if "quantity" in clean:
        if isinstance(clean["quantity"], bool) or not isinstance(clean["quantity"], int) or clean["quantity"] < 0:
            return None, "'quantity' must be a non-negative integer"
    return clean, None


def create_app():
    app = Flask(__name__)
    app.config["INVENTORY"] = []
    app.config["NEXT_ID"] = 1

    def add_item(fields):
        item = {"id": app.config["NEXT_ID"], "name": "", "brand": "",
                "barcode": "", "price": 0.0, "quantity": 0, "ingredients": ""}
        item.update(fields)
        app.config["NEXT_ID"] += 1
        app.config["INVENTORY"].append(item)
        return item

    def find(item_id):
        return next((i for i in app.config["INVENTORY"] if i["id"] == item_id), None)

    @app.get("/")
    def index():
        return jsonify(message="Inventory API is running",
                       endpoints=["/inventory", "/inventory/<id>",
                                  "/external/barcode/<barcode>",
                                  "/external/search?name=",
                                  "/inventory/import"]), 200

    # ---------- CRUD ----------
    @app.get("/inventory")
    def list_items():
        items = app.config["INVENTORY"]
        name = request.args.get("name")
        if name:
            items = [i for i in items if name.lower() in i["name"].lower()]
        return jsonify(items), 200

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        item = find(item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        return jsonify(item), 200

    @app.post("/inventory")
    def create_item():
        clean, err = validate(request.get_json(silent=True))
        if err:
            return jsonify(error=err), 400
        return jsonify(add_item(clean)), 201

    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        item = find(item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        clean, err = validate(request.get_json(silent=True), partial=True)
        if err:
            return jsonify(error=err), 400
        item.update(clean)
        return jsonify(item), 200

    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        item = find(item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        app.config["INVENTORY"].remove(item)
        return jsonify(message="Item deleted"), 200

    # ---------- External API helper routes ----------
    @app.get("/external/barcode/<barcode>")
    def external_barcode(barcode):
        try:
            product = external_api.fetch_by_barcode(barcode)
        except requests.RequestException as exc:
            return jsonify(error=f"External API error: {exc}"), 502
        if not product:
            return jsonify(error="Product not found"), 404
        return jsonify(product), 200

    @app.get("/external/search")
    def external_search():
        name = request.args.get("name")
        if not name:
            return jsonify(error="'name' query parameter is required"), 400
        try:
            return jsonify(external_api.search_by_name(name)), 200
        except requests.RequestException as exc:
            return jsonify(error=f"External API error: {exc}"), 502

    @app.post("/inventory/import")
    def import_item():
        """Fetch a product from OpenFoodFacts and add it to the inventory."""
        data = request.get_json(silent=True) or {}
        barcode, name = data.get("barcode"), data.get("name")
        if not barcode and not name:
            return jsonify(error="Provide 'barcode' or 'name'"), 400
        try:
            if barcode:
                product = external_api.fetch_by_barcode(barcode)
            else:
                results = external_api.search_by_name(name, limit=1)
                product = results[0] if results else None
        except requests.RequestException as exc:
            return jsonify(error=f"External API error: {exc}"), 502
        if not product:
            return jsonify(error="Product not found"), 404
        extras, err = validate({k: data[k] for k in ("price", "quantity") if k in data}, partial=True)
        if err:
            return jsonify(error=err), 400
        product.update(extras)
        return jsonify(add_item(product)), 201

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
