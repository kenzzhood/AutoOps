"""ShopVerse Order Service — order persistence and admin views."""

from __future__ import annotations

import sys
import time
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, "/app/shared")
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse Order Service")
ORDERS: list[dict] = []


class CreateOrder(BaseModel):
    user_id: int
    total: float
    trace_id: str = ""


@app.post("/orders")
def create_order(body: CreateOrder):
    start = time.perf_counter()
    order = {
        "order_id": str(uuid.uuid4()),
        "user_id": body.user_id,
        "total": body.total,
        "trace_id": body.trace_id or str(uuid.uuid4()),
        "status": "confirmed",
    }
    ORDERS.append(order)
    log_event("order-service", path="/orders", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000, order_id=order["order_id"])
    return order


@app.get("/orders")
def list_orders(user_id: int | None = None):
    start = time.perf_counter()
    items = ORDERS if user_id is None else [o for o in ORDERS if o["user_id"] == user_id]
    log_event("order-service", path="/orders", method="GET", status=200, duration_ms=(time.perf_counter() - start) * 1000, count=len(items))
    return {"orders": items}


@app.get("/admin/orders")
def admin_orders():
    return {"orders": ORDERS, "count": len(ORDERS)}


@app.get("/health")
def health():
    return {"service": "order-service", "status": "ok"}
