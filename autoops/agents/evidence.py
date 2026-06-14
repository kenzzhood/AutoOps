"""Evidence Collection Agent — parallel Splunk MCP queries."""

from __future__ import annotations

import asyncio

from autoops.models.config import AutoOpsConfig
from autoops.models.incident import EvidencePackage
from autoops.splunk.mcp_client import SplunkMCPClient
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


def _build_queries(
    alert_name: str,
    services: list[str],
    window: str,
) -> dict[str, str]:
    service_filter = " OR ".join(f'service="{s}"' for s in services) or "service=*"
    return {
        "error_logs": (
            f'index=main sourcetype=autoops ({service_filter}) level=ERROR '
            f"| head 100"
        ),
        "latency_metrics": (
            f'index=main sourcetype=autoops ({service_filter}) '
            f"| stats avg(duration_ms) as avg_ms, p95(duration_ms) as p95_ms by path"
        ),
        "deployment_events": (
            'index=main sourcetype=autoops event_type=deployment OR source=*deploy* '
            "| sort - _time | head 20"
        ),
        "database_metrics": (
            'index=main sourcetype=autoops event_type=db_query '
            "| stats avg(query_duration_ms) as avg_query_ms, count by database"
        ),
        "container_health": (
            'index=main sourcetype=autoops event_type=container_health OR source=docker '
            "| stats latest(status) as status by container"
        ),
    }


async def collect_evidence(
    alert_name: str,
    affected_services: list[str],
    window: str = "30m",
    config: AutoOpsConfig | None = None,
) -> EvidencePackage:
    """Run 5 MCP queries in parallel."""
    config = config or AutoOpsConfig.from_env()
    mcp = SplunkMCPClient(config)
    queries = _build_queries(alert_name, affected_services, window)

    async def _run(key: str, query: str) -> tuple[str, list]:
        try:
            results = await mcp.run_search(query, earliest=f"-{window}", latest="now")
            return key, results
        except Exception as exc:
            logger.warning("Evidence query %s failed: %s", key, exc)
            return key, [{"error": str(exc), "query": query}]

    tasks = [_run(k, q) for k, q in queries.items()]
    gathered = await asyncio.gather(*tasks)

    evidence = EvidencePackage(
        alert_name=alert_name,
        affected_services=affected_services,
        window=window,
        raw_queries=list(queries.values()),
    )

    for key, results in gathered:
        setattr(evidence, key, results)

    logger.info("Collected evidence: %d query groups", len(gathered))
    return evidence
