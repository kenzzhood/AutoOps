"""ShopVerse Notification Service — email dispatch via mock provider."""

from __future__ import annotations

import os
import sys
import time

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

sys.path.insert(0, "/app/shared")
from incidents import STATE  # noqa: E402
from telemetry import log_event  # noqa: E402

app = FastAPI(title="ShopVerse Notification Service")
EMAIL_MOCK_URL = os.getenv("EMAIL_MOCK_URL", "http://email-mock:8006")


class NotifyBody(BaseModel):
    user_id: int
    email: EmailStr
    subject: str
    body: str


@app.post("/notify")
def notify(body: NotifyBody):
    start = time.perf_counter()
    if STATE.dependency_down():
        log_event("notification-service", path="/notify", method="POST", status=503, level="ERROR", duration_ms=(time.perf_counter() - start) * 1000, dependency="email-mock")
        raise HTTPException(503, "Email provider unavailable")
    try:
        resp = httpx.post(f"{EMAIL_MOCK_URL}/send", json=body.model_dump(), timeout=5.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log_event("notification-service", path="/notify", method="POST", status=502, level="ERROR", error=str(exc))
        raise HTTPException(502, "Downstream email failure") from exc
    log_event("notification-service", path="/notify", method="POST", status=200, duration_ms=(time.perf_counter() - start) * 1000)
    return {"sent": True}


@app.get("/health")
def health():
    return {"service": "notification-service", "status": "ok"}
