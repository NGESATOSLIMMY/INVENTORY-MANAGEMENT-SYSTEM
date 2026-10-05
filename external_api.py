"""Thin wrapper around the OpenFoodFacts API (https://world.openfoodfacts.org)."""
import requests

BASE_URL = "https://world.openfoodfacts.org"
TIMEOUT = 10
# OpenFoodFacts asks for: AppName/Version (ContactEmail)
HEADERS = {"User-Agent": "InventoryManagementLab/1.0 (emmanuelngesa0@gmail.com)"}


def _normalize(product):
    """Reduce an OpenFoodFacts product to the fields we care about."""
    return {
        "name": product.get("product_name") or "Unknown product",
        "brand": product.get("brands", ""),
        "barcode": product.get("code") or product.get("_id", ""),
        "ingredients": product.get("ingredients_text", ""),
    }


def fetch_by_barcode(barcode):
    """Return a normalized product dict, or None if not found."""
    resp = requests.get(f"{BASE_URL}/api/v2/product/{barcode}.json",
                        headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in (1, "success") or "product" not in data:
        return None
    product = data["product"]
    product.setdefault("code", barcode)
    return _normalize(product)


def search_by_name(name, limit=5):
    """Return a list of normalized products matching a name."""
    resp = requests.get(f"{BASE_URL}/cgi/search.pl",
                        params={"search_terms": name, "search_simple": 1,
                                "action": "process", "json": 1,
                                "page_size": limit},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return [_normalize(p) for p in resp.json().get("products", [])]
