"""ShopVerse Product Service — catalog and search."""

from __future__ import annotations

import sys
import time

from fastapi import FastAPI, Query

sys.path.insert(0, "/app/shared")
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse Product Service")

PRODUCTS = [
    {"id": 1, "name": "Wireless Headphones", "category": "electronics", "price": 79.99},
    {"id": 2, "name": "Running Shoes", "category": "apparel", "price": 119.0},
    {"id": 3, "name": "Coffee Maker", "category": "home", "price": 49.5},
    {"id": 4, "name": "Desk Lamp", "category": "home", "price": 34.99},
    {"id": 5, "name": "Backpack", "category": "accessories", "price": 59.0},
]


@app.get("/products")
def list_products(category: str | None = None, q: str | None = Query(default=None)):
    start = time.perf_counter()
    items = PRODUCTS
    if category:
        items = [p for p in items if p["category"] == category]
    if q:
        items = [p for p in items if q.lower() in p["name"].lower()]
    log_event("product-service", path="/products", method="GET", status=200, duration_ms=(time.perf_counter() - start) * 1000, count=len(items))
    return {"products": items}


@app.get("/products/{product_id}")
def get_product(product_id: int):
    start = time.perf_counter()
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        log_event("product-service", path=f"/products/{product_id}", method="GET", status=404, level="WARNING", duration_ms=(time.perf_counter() - start) * 1000)
        return {"error": "not found"}
    log_event("product-service", path=f"/products/{product_id}", method="GET", status=200, duration_ms=(time.perf_counter() - start) * 1000)
    return product


@app.get("/health")
def health():
    return {"service": "product-service", "status": "ok"}
