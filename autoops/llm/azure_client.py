"""Azure OpenAI client with forced function calling for structured agent output."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import AzureOpenAI, RateLimitError

from autoops.models.config import AutoOpsConfig
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic-style tool schema to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _get_client(config: AutoOpsConfig) -> AzureOpenAI:
    return AzureOpenAI(
        api_key=config.azure_openai_api_key,
        api_version=config.azure_openai_api_version,
        azure_endpoint=config.azure_openai_endpoint.rstrip("/"),
    )


def call_with_tool(
    config: AutoOpsConfig,
    tool: dict[str, Any],
    user_message: str,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Call Azure OpenAI with a forced tool/function call.
    Returns parsed JSON arguments — never free-text LLM output.
    """
    client = _get_client(config)
    openai_tool = _to_openai_tool(tool)
    tool_name = tool["name"]

    logger.debug("Azure OpenAI tool call: %s", tool_name)

    response = None
    max_attempts = 6
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=config.azure_openai_deployment,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": user_message}],
                tools=[openai_tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
            )
            break
        except RateLimitError:
            wait = min(90, 5 * (2**attempt))
            logger.warning("Azure rate limited for %s, retry in %ss", tool_name, wait)
            if attempt == max_attempts - 1:
                raise
            time.sleep(wait)

    if response is None:
        raise RuntimeError(f"Azure OpenAI call failed for {tool_name}")

    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError(f"Azure OpenAI did not return tool call for {tool_name}")

    arguments = message.tool_calls[0].function.arguments
    if isinstance(arguments, str):
        return json.loads(arguments)
    return arguments
