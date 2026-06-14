"""ShopVerse Auth Service — JWT login and registration."""

from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

sys.path.insert(0, "/app/shared")
from incidents import STATE  # noqa: E402
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse Auth Service")
JWT_SECRET = os.getenv("JWT_SECRET", "shopverse-dev-secret")
USERS: dict[str, dict] = {}


class RegisterBody(BaseModel):
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


@app.post("/register")
def register(body: RegisterBody):
    start = time.perf_counter()
    if body.email in USERS:
        raise HTTPException(400, "Email exists")
    USERS[body.email] = {"password_hash": _hash(body.password), "id": len(USERS) + 1}
    log_event("auth-service", path="/register", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000)
    return {"email": body.email, "user_id": USERS[body.email]["id"]}


@app.post("/login")
def login(body: LoginBody):
    start = time.perf_counter()
    user = USERS.get(body.email)
    if STATE.auth_attack_mode():
        for _ in range(20):
            log_event(
                "auth-service",
                path="/login",
                method="POST",
                status=401,
                level="WARNING",
                event="failed_login",
                reason="credential_stuffing_simulation",
            )
    if not user or user["password_hash"] != _hash(body.password):
        log_event("auth-service", path="/login", method="POST", status=401, level="WARNING", duration_ms=(time.perf_counter() - start) * 1000)
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode(
        {"sub": body.email, "user_id": user["id"], "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        JWT_SECRET,
        algorithm="HS256",
    )
    log_event("auth-service", path="/login", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000, user_id=user["id"])
    return {"access_token": token, "token_type": "bearer", "user_id": user["id"]}


@app.get("/health")
def health():
    return {"service": "auth-service", "status": "ok"}
