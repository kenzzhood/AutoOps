"""Tests for Azure OpenAI client."""

import json
from unittest.mock import MagicMock, patch

from autoops.llm.azure_client import call_with_tool
from autoops.models.config import AutoOpsConfig

SAMPLE_TOOL = {
    "name": "test_tool",
    "description": "Test",
    "input_schema": {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    },
}


def test_call_with_tool_parses_response():
    config = AutoOpsConfig(
        azure_openai_api_key="key",
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_deployment="gpt-4o",
    )

    mock_tool_call = MagicMock()
    mock_tool_call.function.arguments = json.dumps({"value": "ok"})

    mock_message = MagicMock()
    mock_message.tool_calls = [mock_tool_call]

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("autoops.llm.azure_client.AzureOpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create.return_value = mock_response
        result = call_with_tool(config, SAMPLE_TOOL, "hello")

    assert result == {"value": "ok"}
