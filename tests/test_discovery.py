"""Tests for discovery agent."""

from pathlib import Path
from unittest.mock import patch

import pytest

from autoops.agents.discovery import _heuristic_architecture, run_discovery
from autoops.scanner.repo_scanner import scan_repository


@pytest.mark.asyncio
async def test_heuristic_discovery(sample_architecture):
    repo = Path(__file__).parent.parent / "demo-app"
    scan = scan_repository(str(repo))
    arch = _heuristic_architecture(scan)
    assert arch.app_name
    assert len(arch.services) >= 1


@pytest.mark.asyncio
async def test_discovery_without_api_key(config):
    repo = str(Path(__file__).parent.parent / "demo-app")
    arch = await run_discovery(repo, config)
    assert arch.services


@pytest.mark.asyncio
async def test_discovery_with_mock_azure(config, sample_architecture):
    config.azure_openai_api_key = "test-key"
    config.azure_openai_endpoint = "https://test.openai.azure.com/"
    config.azure_openai_deployment = "gpt-4o"

    with patch("autoops.agents.discovery.call_with_tool") as mock_call:
        mock_call.return_value = sample_architecture.model_dump()
        arch = await run_discovery(
            str(Path(__file__).parent.parent / "demo-app"), config
        )
    assert arch.app_name == "demo-shop"
