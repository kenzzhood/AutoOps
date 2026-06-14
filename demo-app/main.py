"""FastAPI demo app with checkout N+1 bug toggle."""

from __future__ import annotations

import hashlib
import logging
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal, get_db, init_db
from models import BugToggle, CartItem, Order, OrderItem, Product, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo-app")

BUG_ENABLED = False
N1_SLEEP_MS = float(os.getenv("N1_SLEEP_MS", "40"))
TIMEOUT_ERROR_RATE = float(os.getenv("TIMEOUT_ERROR_RATE", "0.12"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        if not db.query(Product).count():
            db.add_all(
                [
                    Product(name="Widget A", price=19.99),
                    Product(name="Widget B", price=29.99),
                    Product(name="Widget C", price=9.99),
                    Product(name="Gadget X", price=49.99),
                    Product(name="Gadget Y", price=59.99),
                ]
            )
        if not db.query(BugToggle).first():
            db.add(BugToggle(id=1, enabled=False))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="AutoOps Demo Shop", lifespan=lifespan)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CheckoutRequest(BaseModel):
    user_id: int


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _get_bug_state(db: Session) -> bool:
    global BUG_ENABLED
    toggle = db.query(BugToggle).first()
    if toggle:
        BUG_ENABLED = toggle.enabled
    return BUG_ENABLED


@app.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, password_hash=_hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered: %s", user.email)
    return {"user_id": user.id, "email": user.email}


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or user.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    logger.info("User login: %s", user.email)
    return {"user_id": user.id, "email": user.email}


@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [{"id": p.id, "name": p.name, "price": p.price} for p in products]


@app.post("/checkout")
def checkout(req: CheckoutRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cart_items = db.query(CartItem).filter(CartItem.user_id == req.user_id).all()
    if not cart_items:
        # Seed cart for demo if empty
        products = db.query(Product).limit(3).all()
        for p in products:
            db.add(CartItem(user_id=req.user_id, product_id=p.id, quantity=1))
        db.commit()
        cart_items = db.query(CartItem).filter(CartItem.user_id == req.user_id).all()

    bug_on = _get_bug_state(db)

    try:
        if bug_on:
            total = _checkout_n_plus_one(db, cart_items)
        else:
            total = _checkout_efficient(db, req.user_id)

        if bug_on and random.random() < TIMEOUT_ERROR_RATE:
            raise HTTPException(status_code=500, detail="Checkout timeout — database overloaded")

        order = Order(user_id=req.user_id, total=total)
        db.add(order)
        db.flush()

        if bug_on:
            for item in cart_items:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                db.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        price=product.price if product else 0,
                    )
                )
        else:
            rows = (
                db.query(CartItem, Product)
                .join(Product, CartItem.product_id == Product.id)
                .filter(CartItem.user_id == req.user_id)
                .all()
            )
            for cart, product in rows:
                db.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=cart.quantity,
                        price=product.price,
                    )
                )

        db.query(CartItem).filter(CartItem.user_id == req.user_id).delete()
        db.commit()

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Checkout complete user=%s total=%.2f duration_ms=%.1f bug=%s trace_id=%s",
            req.user_id,
            total,
            duration_ms,
            bug_on,
            trace_id,
        )
        return {
            "order_id": order.id,
            "total": total,
            "duration_ms": round(duration_ms, 2),
            "trace_id": trace_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Checkout failed: %s trace_id=%s", exc, trace_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _checkout_efficient(db: Session, user_id: int) -> float:
    """Single JOIN query — ~50ms."""
    rows = (
        db.query(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .filter(CartItem.user_id == user_id)
        .all()
    )
    return sum(c.quantity * p.price for c, p in rows)


def _checkout_n_plus_one(db: Session, cart_items: list[CartItem]) -> float:
    """N+1 queries — one per cart item, ~800ms with sleep."""
    total = 0.0
    for item in cart_items:
        time.sleep(N1_SLEEP_MS / 1000.0)
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            total += item.quantity * product.price
    return total


@app.get("/orders/{user_id}")
def get_orders(user_id: int, db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .all()
    )
    return [
        {
            "order_id": o.id,
            "total": o.total,
            "items": [
                {"product_id": i.product_id, "quantity": i.quantity, "price": i.price}
                for i in o.items
            ],
        }
        for o in orders
    ]


@app.post("/admin/toggle-bug")
def toggle_bug(enabled: Optional[bool] = None, db: Session = Depends(get_db)):
    global BUG_ENABLED
    toggle = db.query(BugToggle).first()
    if not toggle:
        toggle = BugToggle(id=1, enabled=False)
        db.add(toggle)
    if enabled is not None:
        toggle.enabled = enabled
    else:
        toggle.enabled = not toggle.enabled
    BUG_ENABLED = toggle.enabled
    db.commit()
    logger.warning("Bug toggle set to: %s", BUG_ENABLED)
    return {"bug_enabled": BUG_ENABLED, "message": "N+1 checkout bug " + ("ENABLED" if BUG_ENABLED else "DISABLED")}


@app.get("/health")
def health():
    return {"status": "ok", "bug_enabled": BUG_ENABLED}
