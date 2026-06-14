"""Tests for RCA agent."""

from unittest.mock import patch

import pytest

from autoops.agents.rca import _heuristic_rca, run_rca
from autoops.models.incident import EvidencePackage


@pytest.mark.asyncio
async def test_heuristic_rca(sample_architecture):
    evidence = EvidencePackage(
        alert_name="checkout_error",
        affected_services=["main"],
        window="30m",
        deployment_events=[{"time": "14:32", "version": "v2.4.7"}],
        database_metrics=[{"avg_query_ms": 450}],
    )
    causes = _heuristic_rca(evidence, sample_architecture)
    assert len(causes) >= 1
    assert causes[0].confidence >= 0.5


@pytest.mark.asyncio
async def test_rca_with_mock_azure(config, sample_architecture):
    evidence = EvidencePackage(
        alert_name="checkout_error",
        affected_services=["main"],
        window="30m",
        deployment_events=[{"time": "14:32"}],
    )
    config.azure_openai_api_key = "test-key"
    config.azure_openai_endpoint = "https://test.openai.azure.com/"
    config.azure_openai_deployment = "gpt-4o"

    with patch("autoops.agents.rca.call_with_tool") as mock_call:
        mock_call.return_value = {
            "root_causes": [
                {
                    "hypothesis": "Deployment at 14:32 caused N+1 regression",
                    "confidence": 0.92,
                    "evidence": ["Error spike 3 min after deploy"],
                    "component": "checkout",
                }
            ]
        }
        causes = await run_rca(evidence, sample_architecture, config)

    assert causes[0].confidence == 0.92
