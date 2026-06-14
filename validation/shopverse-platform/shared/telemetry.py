"""Structured telemetry logging for ShopVerse services."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("shopverse")


def log_event(
    service: str,
    *,
    path: str = "",
    method: str = "GET",
    status: int = 200,
    duration_ms: float = 0,
    level: str = "INFO",
    **extra: object,
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "trace_id": extra.pop("trace_id", str(uuid.uuid4())),
        "level": level,
        "sourcetype": "autoops",
        **extra,
    }
    logger.info(json.dumps(event))
    hec_url = os.getenv("SPLUNK_HEC_URL", "")
    hec_token = os.getenv("SPLUNK_HEC_TOKEN", "")
    if hec_url and hec_token:
        try:
            httpx.post(
                hec_url,
                headers={"Authorization": f"Splunk {hec_token}"},
                json={"event": event, "sourcetype": "autoops", "index": "main"},
                timeout=3.0,
                verify=False,
            )
        except httpx.HTTPError:
            pass
