"""ShopVerse API Gateway — routing, admin incidents, orchestration."""

from __future__ import annotations

import os
import sys
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, "/app/shared")
from incidents import INCIDENT_TYPES, STATE  # noqa: E402
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse API Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_URL = os.getenv("AUTH_URL", "http://auth-service:8001")
PRODUCT_URL = os.getenv("PRODUCT_URL", "http://product-service:8002")
CHECKOUT_URL = os.getenv("CHECKOUT_URL", "http://checkout-service:8003")
ORDER_URL = os.getenv("ORDER_URL", "http://order-service:8004")
NOTIFY_URL = os.getenv("NOTIFY_URL", "http://notification-service:8005")


async def _proxy(method: str, url: str, request: Request) -> JSONResponse:
    start = time.perf_counter()
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, content=body, headers=headers, params=request.query_params)
    log_event(
        "api-gateway",
        path=str(request.url.path),
        method=method,
        status=resp.status_code,
        duration_ms=(time.perf_counter() - start) * 1000,
        upstream=url,
    )
    return JSONResponse(resp.json() if resp.content else {}, status_code=resp.status_code)


@app.post("/admin/incidents/enable")
def enable_incident(type: str):
    if type not in INCIDENT_TYPES:
        raise HTTPException(400, f"Unknown type. Valid: {INCIDENT_TYPES}")
    return STATE.enable(type)


@app.post("/admin/incidents/disable")
def disable_incident():
    return STATE.disable()


@app.get("/admin/incidents/status")
def incident_status():
    return STATE.status()


@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def auth_proxy(path: str, request: Request):
    return await _proxy(request.method, f"{AUTH_URL}/{path}", request)


@app.get("/api/products/{product_id}")
async def product_detail(product_id: int, request: Request):
    return await _proxy("GET", f"{PRODUCT_URL}/products/{product_id}", request)


@app.api_route("/api/products/{path:path}", methods=["GET", "POST"])
async def product_proxy(path: str, request: Request):
    return await _proxy(request.method, f"{PRODUCT_URL}/{path}", request)


@app.get("/api/products")
async def products_root(request: Request):
    return await _proxy("GET", f"{PRODUCT_URL}/products", request)


@app.api_route("/api/checkout/{path:path}", methods=["GET", "POST"])
async def checkout_proxy(path: str, request: Request):
    return await _proxy(request.method, f"{CHECKOUT_URL}/{path}", request)


@app.post("/api/checkout")
async def checkout_root(request: Request):
    start = time.perf_counter()
    body = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        checkout_resp = await client.post(f"{CHECKOUT_URL}/checkout", json=body)
        if checkout_resp.status_code >= 400:
            return JSONResponse(checkout_resp.json(), status_code=checkout_resp.status_code)
        checkout_data = checkout_resp.json()
        order_resp = await client.post(
            f"{ORDER_URL}/orders",
            json={
                "user_id": body.get("user_id"),
                "total": checkout_data.get("order_total", 0),
                "trace_id": checkout_data.get("trace_id", ""),
            },
        )
        notify_resp = await client.post(
            f"{NOTIFY_URL}/notify",
            json={
                "user_id": body.get("user_id"),
                "email": f"user{body.get('user_id')}@shopverse.test",
                "subject": "Order confirmed",
                "body": f"Your order total is {checkout_data.get('order_total')}",
            },
        )
    log_event("api-gateway", path="/api/checkout", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000)
    return {
        "checkout": checkout_data,
        "order": order_resp.json() if order_resp.status_code < 400 else {"error": order_resp.text},
        "notification": notify_resp.json() if notify_resp.status_code < 400 else {"error": notify_resp.text},
    }


@app.get("/api/orders")
async def orders(request: Request):
    return await _proxy("GET", f"{ORDER_URL}/orders", request)


@app.get("/api/admin/orders")
async def admin_orders(request: Request):
    return await _proxy("GET", f"{ORDER_URL}/admin/orders", request)


@app.get("/health")
def health():
    return {"service": "api-gateway", "status": "ok", "incident": STATE.status()}
