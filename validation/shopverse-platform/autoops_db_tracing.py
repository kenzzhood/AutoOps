"""SQLAlchemy query tracing for AutoOps observability."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("autoops.db")

DATABASE_NAME = "postgresql"


def _emit(event_type: str, **fields) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "database": DATABASE_NAME,
        "sourcetype": "autoops",
        "level": "INFO",
        **fields,
    }
    logger.info(json.dumps(payload))


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_list = conn.info.get("query_start_time", [])
    if not start_list:
        return
    start = start_list.pop()
    duration_ms = (time.perf_counter() - start) * 1000
    _emit(
        "db_query",
        query_duration_ms=round(duration_ms, 2),
        statement=statement[:500],
    )


def install_db_tracing(engine: Engine) -> None:
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)