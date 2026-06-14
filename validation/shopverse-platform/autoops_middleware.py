"""FastAPI middleware for structured JSON logging to Splunk HEC."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("autoops.middleware")

SERVICE_NAME = "main"
SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")


def _log_level(status: int) -> str:
    if status >= 500:
        return "ERROR"
    if status >= 400:
        return "WARNING"
    return "INFO"


class AutoOpsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        user_id = request.headers.get("X-User-Id", "")

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        level = _log_level(response.status_code)

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": SERVICE_NAME,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "trace_id": trace_id,
            "user_id": user_id,
            "level": level,
            "sourcetype": "autoops",
        }

        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(json.dumps(event))

        if SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        SPLUNK_HEC_URL,
                        headers={
                            "Authorization": f"Splunk {SPLUNK_HEC_TOKEN}",
                            "Content-Type": "application/json",
                        },
                        json={"event": event, "sourcetype": "autoops", "index": "main"},
                    )
            except Exception:
                pass

        response.headers["X-Trace-Id"] = trace_id
        return response


def install_middleware(app) -> None:
    app.add_middleware(AutoOpsMiddleware)