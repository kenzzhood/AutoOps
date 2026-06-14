"""Incident injection framework — Redis-backed for multi-service Docker."""

from __future__ import annotations

import json
import os
import random
import threading
import time
from typing import Any

try:
    import redis
except ImportError:
    redis = None  # type: ignore

INCIDENT_TYPES = (
    "n_plus_one",
    "db_latency",
    "api_failure",
    "memory_leak",
    "cpu_spike",
    "dependency_failure",
    "auth_attack",
)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
KEY = "shopverse:incident"


class IncidentState:
    def __init__(self) -> None:
        self._local_memory: list[dict[str, Any]] = []
        self._cpu_stop = threading.Event()
        self._cpu_thread: threading.Thread | None = None
        self._redis = redis.from_url(REDIS_URL, decode_responses=True) if redis else None

    def _get_active(self) -> str | None:
        if self._redis:
            return self._redis.get(KEY)
        return getattr(self, "_active_local", None)

    def _set_active(self, value: str | None) -> None:
        if self._redis:
            if value:
                self._redis.set(KEY, value)
            else:
                self._redis.delete(KEY)
        else:
            self._active_local = value

    def enable(self, incident_type: str) -> dict[str, str]:
        if incident_type not in INCIDENT_TYPES:
            raise ValueError(f"Unknown incident type: {incident_type}")
        self.disable()
        self._set_active(incident_type)
        if incident_type == "cpu_spike":
            self._start_cpu_worker()
        return {"status": "enabled", "type": incident_type}

    def disable(self) -> dict[str, str]:
        prev = self._get_active()
        self._set_active(None)
        self._local_memory.clear()
        self._cpu_stop.set()
        if self._cpu_thread and self._cpu_thread.is_alive():
            self._cpu_thread.join(timeout=1)
        self._cpu_stop.clear()
        self._cpu_thread = None
        return {"status": "disabled", "previous": prev or "none"}

    def status(self) -> dict[str, Any]:
        return {
            "active": self._get_active(),
            "memory_cache_size": len(self._local_memory),
            "cpu_worker": self._cpu_thread is not None and self._cpu_thread.is_alive(),
        }

    @property
    def active(self) -> str | None:
        return self._get_active()

    def maybe_fail_api(self) -> None:
        if self._get_active() == "api_failure" and random.random() < 0.25:
            raise RuntimeError("Injected API failure")

    def db_delay(self) -> None:
        if self._get_active() == "db_latency":
            time.sleep(0.15 + random.random() * 0.1)

    def leak_memory(self, payload: dict[str, Any]) -> None:
        if self._get_active() == "memory_leak":
            self._local_memory.append(payload)

    def auth_attack_mode(self) -> bool:
        return self._get_active() == "auth_attack"

    def dependency_down(self) -> bool:
        return self._get_active() == "dependency_failure"

    def n_plus_one_mode(self) -> bool:
        return self._get_active() == "n_plus_one"

    def _start_cpu_worker(self) -> None:
        def _burn() -> None:
            x = 0
            while not self._cpu_stop.is_set():
                x = (x * 31 + 7) % 10_000_000

        self._cpu_thread = threading.Thread(target=_burn, daemon=True)
        self._cpu_thread.start()


STATE = IncidentState()
