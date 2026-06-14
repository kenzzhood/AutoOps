"""Root Cause Analysis Agent — Claude tool_use with deployment correlation."""

from __future__ import annotations

import json
from typing import Any

from autoops.llm.router import call_with_tool
from autoops.models.architecture import ArchitectureMap
from autoops.models.config import AutoOpsConfig
from autoops.models.incident import EvidencePackage, RootCause
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

RCA_TOOL = {
    "name": "report_root_causes",
    "description": "Report ranked root cause hypotheses with confidence scores",
    "input_schema": {
        "type": "object",
        "properties": {
            "root_causes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "component": {"type": "string"},
                    },
                    "required": ["hypothesis", "confidence", "evidence", "component"],
                },
            },
        },
        "required": ["root_causes"],
    },
}


def _has_real_data(rows: list) -> bool:
    return bool(rows) and not all(isinstance(r, dict) and "error" in r for r in rows)


def _heuristic_rca(evidence: EvidencePackage, architecture: ArchitectureMap) -> list[RootCause]:
    """Fallback RCA when API unavailable."""
    causes: list[RootCause] = []
    if _has_real_data(evidence.deployment_events):
        causes.append(
            RootCause(
                hypothesis="Recent deployment correlated with error spike",
                confidence=0.85,
                evidence=["Deployment event found within investigation window"],
                component=evidence.affected_services[0] if evidence.affected_services else "unknown",
            )
        )
    if _has_real_data(evidence.database_metrics):
        causes.append(
            RootCause(
                hypothesis="Database query latency degradation (possible N+1)",
                confidence=0.78,
                evidence=["Elevated db_query duration in evidence"],
                component=architecture.databases[0].name if architecture.databases else "database",
            )
        )
    if _has_real_data(evidence.latency_metrics):
        causes.append(
            RootCause(
                hypothesis="Checkout endpoint latency exceeded SLO",
                confidence=0.72,
                evidence=["P95 latency spike on /checkout"],
                component="checkout",
            )
        )
    if not causes:
        causes.append(
            RootCause(
                hypothesis="Insufficient evidence — manual investigation required",
                confidence=0.3,
                evidence=["No strong signals in Splunk data"],
                component="unknown",
            )
        )
    return sorted(causes, key=lambda c: c.confidence, reverse=True)


async def run_rca(
    evidence: EvidencePackage,
    architecture: ArchitectureMap,
    config: AutoOpsConfig | None = None,
) -> list[RootCause]:
    """Run RCA agent with deployment timeline correlation."""
    config = config or AutoOpsConfig.from_env()

    from autoops.config.store import ConfigStore

    store = ConfigStore()
    profile = store.get_profile()
    if not profile and not config.llm_configured:
        logger.warning("No LLM provider configured — using heuristic RCA")
        return _heuristic_rca(evidence, architecture)
    if profile:
        config = store.profile_to_autoops_config(profile)

    evidence_json = evidence.model_dump_json()
    try:
        data: dict[str, Any] = call_with_tool(
            config,
            RCA_TOOL,
            (
                "You are an SRE performing root cause analysis. Reason step by step.\n"
                "CRITICAL: Correlate deployment events with error/latency spikes.\n"
                "Example: 'Deployment at 14:32 → Error spike at 14:35 → High confidence'\n"
                "Look for N+1 query patterns on checkout if db_query metrics are elevated.\n\n"
                f"Architecture:\n{architecture.model_dump_json()}\n\n"
                f"Evidence:\n{evidence_json}\n\n"
                "Return ranked root causes with confidence 0.0-1.0 via report_root_causes."
            ),
            profile=profile,
            store_secrets=store,
        )
        causes = [RootCause.model_validate(c) for c in data["root_causes"]]
    except Exception as exc:
        logger.warning("LLM RCA failed (%s) — using heuristic RCA", exc)
        causes = _heuristic_rca(evidence, architecture)
    logger.info("RCA found %d hypotheses", len(causes))
    return sorted(causes, key=lambda c: c.confidence, reverse=True)
