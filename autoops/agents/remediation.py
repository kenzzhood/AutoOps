"""Remediation + Reporting Agent — Claude tool_use."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from autoops.llm.router import call_with_tool
from autoops.models.architecture import ArchitectureMap
from autoops.models.config import AutoOpsConfig
from autoops.models.incident import (
    EvidencePackage,
    ImpactAssessment,
    Incident,
    RemediationStep,
    RootCause,
)
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

REMEDIATION_TOOL = {
    "name": "report_incident",
    "description": "Generate full incident report with impact and remediation",
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            "impact": {
                "type": "object",
                "properties": {
                    "users_affected_estimate": {"type": "integer"},
                    "revenue_impact": {"type": "string"},
                    "services_degraded": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["users_affected_estimate", "revenue_impact", "services_degraded"],
            },
            "remediation_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "command": {"type": "string"},
                        "risk": {"type": "string"},
                        "estimated_time_minutes": {"type": "integer"},
                    },
                    "required": ["action", "risk", "estimated_time_minutes"],
                },
            },
            "executive_summary": {"type": "string"},
            "technical_summary": {"type": "string"},
            "error_rate": {"type": "number"},
        },
        "required": [
            "severity",
            "impact",
            "remediation_steps",
            "executive_summary",
            "technical_summary",
        ],
    },
}


def _heuristic_remediation(
    alert_name: str,
    root_causes: list[RootCause],
    evidence: EvidencePackage,
    architecture: ArchitectureMap,
    duration_seconds: float,
) -> Incident:
    top = root_causes[0] if root_causes else None
    steps = [
        RemediationStep(
            action="Disable N+1 bug toggle if enabled",
            command="curl -X POST http://localhost:8080/admin/incidents/disable",
            risk="low",
            estimated_time_minutes=1,
        ),
        RemediationStep(
            action="Rollback to previous deployment",
            command="git revert HEAD && docker compose up -d --build demo-app",
            risk="medium",
            estimated_time_minutes=10,
        ),
    ]
    return Incident(
        id=str(uuid.uuid4()),
        alert_name=alert_name,
        severity="high" if top and top.confidence > 0.7 else "medium",
        started_at=datetime.now(timezone.utc),
        affected_services=evidence.affected_services,
        error_rate=12.0,
        root_causes=root_causes,
        impact=ImpactAssessment(
            users_affected_estimate=500,
            revenue_impact="high" if "/checkout" in alert_name.lower() else "medium",
            services_degraded=evidence.affected_services,
        ),
        remediation_steps=steps,
        executive_summary=(
            f"Checkout service degraded due to {top.hypothesis if top else 'unknown issue'}. "
            "Immediate rollback recommended to restore service."
        ),
        technical_summary=(
            f"Alert '{alert_name}' triggered. Top RCA: "
            f"{top.hypothesis if top else 'N/A'} (confidence {top.confidence if top else 0}). "
            f"Architecture: {architecture.app_name}."
        ),
        investigation_duration_seconds=duration_seconds,
    )


async def run_remediation(
    alert_name: str,
    root_causes: list[RootCause],
    evidence: EvidencePackage,
    architecture: ArchitectureMap,
    duration_seconds: float,
    config: AutoOpsConfig | None = None,
) -> Incident:
    """Generate incident report with remediation steps."""
    config = config or AutoOpsConfig.from_env()

    from autoops.config.store import ConfigStore

    store = ConfigStore()
    profile = store.get_profile()
    if not profile and not config.llm_configured:
        logger.warning("No LLM provider configured — using heuristic remediation")
        return _heuristic_remediation(
            alert_name, root_causes, evidence, architecture, duration_seconds
        )
    if profile:
        config = store.profile_to_autoops_config(profile)

    try:
        data: dict[str, Any] = call_with_tool(
            config,
            REMEDIATION_TOOL,
            (
                "Generate a complete incident report for executives and engineers.\n"
                "Include specific remediation commands where applicable.\n\n"
                f"Alert: {alert_name}\n"
                f"Root causes: {[c.model_dump() for c in root_causes]}\n"
                f"Evidence summary: errors={len(evidence.error_logs)}, "
                f"deployments={len(evidence.deployment_events)}\n"
                f"Architecture: {architecture.app_name}\n"
            ),
            profile=profile,
            store_secrets=store,
        )
        return Incident(
            id=str(uuid.uuid4()),
            alert_name=alert_name,
            severity=data["severity"],
            started_at=datetime.now(timezone.utc),
            affected_services=evidence.affected_services,
            error_rate=data.get("error_rate"),
            root_causes=root_causes,
            impact=ImpactAssessment.model_validate(data["impact"]),
            remediation_steps=[
                RemediationStep.model_validate(s) for s in data["remediation_steps"]
            ],
            executive_summary=data["executive_summary"],
            technical_summary=data["technical_summary"],
            investigation_duration_seconds=duration_seconds,
        )
    except Exception as exc:
        logger.warning("LLM remediation failed (%s) — using heuristic remediation", exc)
        return _heuristic_remediation(
            alert_name, root_causes, evidence, architecture, duration_seconds
        )
