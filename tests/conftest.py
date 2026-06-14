"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoops.models.architecture import ArchitectureMap
from autoops.models.config import AutoOpsConfig

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_architecture() -> ArchitectureMap:
    data = json.loads((FIXTURES / "sample_architecture.json").read_text())
    return ArchitectureMap.model_validate(data)


@pytest.fixture
def config(tmp_path) -> AutoOpsConfig:
    return AutoOpsConfig(
        azure_openai_api_key="",
        azure_openai_endpoint="",
        azure_openai_deployment="",
        splunk_url="http://localhost:8000",
        splunk_username="admin",
        splunk_password="changeme",
        splunk_token="test-token",
        splunk_mcp_url="http://localhost:8089",
        data_dir=tmp_path,
    )
