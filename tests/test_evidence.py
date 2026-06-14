"""Tests for evidence collection agent."""

from unittest.mock import AsyncMock, patch

import pytest

from autoops.agents.evidence import collect_evidence


@pytest.mark.asyncio
async def test_collect_evidence_parallel(config):
    mock_results = [{"level": "ERROR", "path": "/checkout"}]

    with patch("autoops.agents.evidence.SplunkMCPClient") as mock_cls:
        client = AsyncMock()
        client.run_search = AsyncMock(return_value=mock_results)
        mock_cls.return_value = client

        evidence = await collect_evidence(
            "checkout_error_rate", ["main"], "30m", config
        )

    assert evidence.alert_name == "checkout_error_rate"
    assert len(evidence.raw_queries) == 5
    assert len(evidence.error_logs) >= 1
