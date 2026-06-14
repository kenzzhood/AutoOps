"""Tests for remediation agent."""

from unittest.mock import patch

import pytest

from autoops.agents.remediation import _heuristic_remediation, run_remediation
from autoops.models.incident import EvidencePackage, RootCause


@pytest.mark.asyncio
async def test_heuristic_remediation(sample_architecture):
    evidence = EvidencePackage(
        alert_name="checkout_error_rate",
        affected_services=["main"],
        window="30m",
    )
    causes = [
        RootCause(
            hypothesis="N+1 query regression",
            confidence=0.9,
            evidence=["db latency"],
            component="checkout",
        )
    ]
    incident = _heuristic_remediation(
        "checkout_error_rate", causes, evidence, sample_architecture, 12.5
    )
    assert incident.severity in ("critical", "high", "medium", "low")
    assert len(incident.remediation_steps) >= 1
    assert incident.investigation_duration_seconds == 12.5


@pytest.mark.asyncio
async def test_remediation_with_mock_claude(config, sample_architecture):
    evidence = EvidencePackage(
        alert_name="checkout_error_rate",
        affected_services=["main"],
        window="30m",
    )
    causes = [
        RootCause(
            hypothesis="N+1",
            confidence=0.9,
            evidence=["latency"],
            component="checkout",
        )
    ]
    config.azure_openai_api_key = "test-key"
    config.azure_openai_endpoint = "https://test.openai.azure.com/"
    config.azure_openai_deployment = "gpt-4o"

    with patch("autoops.agents.remediation.call_with_tool") as mock_call:
        mock_call.return_value = {
            "severity": "high",
            "impact": {
                "users_affected_estimate": 1000,
                "revenue_impact": "high",
                "services_degraded": ["main"],
            },
            "remediation_steps": [
                {
                    "action": "Rollback deployment",
                    "command": "git revert HEAD",
                    "risk": "medium",
                    "estimated_time_minutes": 10,
                }
            ],
            "executive_summary": "Checkout degraded due to database regression.",
            "technical_summary": "N+1 queries detected on /checkout.",
            "error_rate": 12.5,
        }
        incident = await run_remediation(
            "checkout_error_rate", causes, evidence, sample_architecture, 5.0, config
        )

    assert incident.severity == "high"
    assert "Checkout" in incident.executive_summary
