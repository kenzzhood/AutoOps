"""Tests for multi-provider LLM router."""

import json
from unittest.mock import MagicMock, patch

from autoops.llm.providers import ProviderKind, ProviderProfile
from autoops.llm.router import _to_openai_tool, call_with_tool
from autoops.models.config import AutoOpsConfig

TOOL = {
    "name": "test",
    "description": "t",
    "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
}


def test_to_openai_tool():
    ot = _to_openai_tool(TOOL)
    assert ot["function"]["name"] == "test"


def test_router_azure():
    config = AutoOpsConfig(
        azure_openai_api_key="k",
        azure_openai_endpoint="https://x.openai.azure.com/",
        azure_openai_deployment="gpt-4o",
    )
    profile = ProviderProfile(
        name="default",
        provider=ProviderKind.AZURE_OPENAI,
        endpoint="https://x.openai.azure.com/",
        deployment="gpt-4o",
    )
    with patch("autoops.llm.azure_client.call_with_tool", return_value={"x": "ok"}):
        result = call_with_tool(config, TOOL, "hi", profile=profile)
    assert result == {"x": "ok"}


def test_router_openai():
    config = AutoOpsConfig()
    profile = ProviderProfile(name="default", provider=ProviderKind.OPENAI, model="gpt-4o")
    mock_msg = MagicMock()
    mock_msg.tool_calls = [MagicMock(function=MagicMock(arguments=json.dumps({"x": "ok"})))]
    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value.choices = [
            MagicMock(message=mock_msg)
        ]
        with patch("autoops.config.store.ConfigStore") as mock_store:
            mock_store.return_value.get_profile.return_value = profile
            mock_store.return_value.get_secret.return_value = "sk-test"
            result = call_with_tool(config, TOOL, "hi", profile=profile, store_secrets=mock_store.return_value)
    assert result == {"x": "ok"}
