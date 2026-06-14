"""Email provider mock for dependency failure testing."""

from __future__ import annotations

import time

from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Email Provider Mock")
SENT: list[dict] = []


class SendBody(BaseModel):
    user_id: int
    email: EmailStr
    subject: str
    body: str


@app.post("/send")
def send(body: SendBody):
    time.sleep(0.01)
    payload = body.model_dump()
    SENT.append(payload)
    return {"message_id": f"msg-{len(SENT)}", "status": "queued"}


@app.get("/health")
def health():
    return {"service": "email-mock", "status": "ok", "sent": len(SENT)}
