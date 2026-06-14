"""ShopVerse Checkout Service — cart, checkout, N+1 and DB latency incidents."""

from __future__ import annotations

import os
import sys
import time
import uuid

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

sys.path.insert(0, "/app/shared")
from incidents import STATE  # noqa: E402
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse Checkout Service")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shopverse:shopverse@postgres:5432/shopverse")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class CartItemRow(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    product_id = Column(Integer)
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)


class ProductRow(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(120))
    price = Column(Float)


Base.metadata.create_all(engine)
db = SessionLocal()
if not db.query(ProductRow).count():
    db.add_all(
        [
            ProductRow(id=1, name="Wireless Headphones", price=79.99),
            ProductRow(id=2, name="Running Shoes", price=119.0),
            ProductRow(id=3, name="Coffee Maker", price=49.5),
        ]
    )
    db.commit()
db.close()


class CheckoutBody(BaseModel):
    user_id: int


@app.post("/cart/add")
def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    start = time.perf_counter()
    STATE.db_delay()
    db = SessionLocal()
    product = db.query(ProductRow).filter(ProductRow.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    db.add(CartItemRow(user_id=user_id, product_id=product_id, quantity=quantity, price=product.price))
    db.commit()
    redis_client.incr(f"cart_ops:{user_id}")
    log_event("checkout-service", path="/cart/add", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000, user_id=user_id)
    db.close()
    return {"ok": True}


@app.post("/checkout")
def checkout(body: CheckoutBody):
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    STATE.leak_memory({"user_id": body.user_id, "trace_id": trace_id})
    try:
        STATE.maybe_fail_api()
        STATE.db_delay()
        db = SessionLocal()
        items = db.query(CartItemRow).filter(CartItemRow.user_id == body.user_id).all()
        if not items:
            for pid in (1, 2, 3):
                db.add(CartItemRow(user_id=body.user_id, product_id=pid, quantity=1, price=10.0))
            db.commit()
            items = db.query(CartItemRow).filter(CartItemRow.user_id == body.user_id).all()

        total = 0.0
        if STATE.n_plus_one_mode():
            for item in items:
                time.sleep(0.03)
                product = db.query(ProductRow).filter(ProductRow.id == item.product_id).first()
                if product:
                    total += product.price * item.quantity
        else:
            rows = db.query(CartItemRow, ProductRow).join(ProductRow, CartItemRow.product_id == ProductRow.id).filter(CartItemRow.user_id == body.user_id).all()
            total = sum(c.quantity * p.price for c, p in rows)

        db.query(CartItemRow).filter(CartItemRow.user_id == body.user_id).delete()
        db.commit()
        db.close()
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(
            "checkout-service",
            path="/checkout",
            method="POST",
            status=200,
            duration_ms=duration_ms,
            user_id=body.user_id,
            trace_id=trace_id,
            total=total,
        )
        return {"order_total": total, "trace_id": trace_id, "duration_ms": duration_ms}
    except Exception as exc:
        log_event("checkout-service", path="/checkout", method="POST", status=500, level="ERROR", duration_ms=(time.perf_counter() - start) * 1000, error=str(exc))
        raise HTTPException(500, str(exc)) from exc


@app.get("/health")
def health():
    return {"service": "checkout-service", "status": "ok"}
