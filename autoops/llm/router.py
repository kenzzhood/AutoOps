"""Multi-provider structured tool-call router."""

from __future__ import annotations

import json
import os
from typing import Any

from autoops.llm.providers import ProviderKind, ProviderProfile
from autoops.models.config import AutoOpsConfig
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _parse_openai_tool_response(message: Any, tool_name: str) -> dict[str, Any]:
    if not message.tool_calls:
        raise RuntimeError(f"No tool call returned for {tool_name}")
    arguments = message.tool_calls[0].function.arguments
    if isinstance(arguments, str):
        return json.loads(arguments)
    return arguments


def _call_openai_compatible(
    api_key: str,
    base_url: str | None,
    model: str,
    tool: dict[str, Any],
    user_message: str,
    max_tokens: int,
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    openai_tool = _to_openai_tool(tool)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": user_message}],
        tools=[openai_tool],
        tool_choice={"type": "function", "function": {"name": tool["name"]}},
    )
    return _parse_openai_tool_response(response.choices[0].message, tool["name"])


def _call_azure(config: AutoOpsConfig, tool: dict, user_message: str, max_tokens: int) -> dict:
    from autoops.llm.azure_client import call_with_tool

    return call_with_tool(config, tool, user_message, max_tokens)


def _call_claude(api_key: str, model: str, tool: dict, user_message: str, max_tokens: int) -> dict:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user_message}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            return block.input
    raise RuntimeError(f"Claude did not return tool {tool['name']}")


def _call_bedrock(profile: ProviderProfile, tool: dict, user_message: str, max_tokens: int) -> dict:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=profile.region)
    openai_tool = _to_openai_tool(tool)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_message}],
        "tools": [
            {
                "name": openai_tool["function"]["name"],
                "description": openai_tool["function"]["description"],
                "input_schema": openai_tool["function"]["parameters"],
            }
        ],
        "tool_choice": {"type": "tool", "name": tool["name"]},
    }
    model_id = profile.model or "anthropic.claude-3-5-sonnet-20241022-v2:0"
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    for block in payload.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
            return block.get("input", {})
    raise RuntimeError(f"Bedrock did not return tool {tool['name']}")


def call_with_tool(
    config: AutoOpsConfig,
    tool: dict[str, Any],
    user_message: str,
    max_tokens: int = 4096,
    profile: ProviderProfile | None = None,
    store_secrets: Any | None = None,
) -> dict[str, Any]:
    """
    Dispatch structured tool call to the active provider.
    Uses profile from config.extra_profile or env fallbacks.
    """
    profile = profile or getattr(config, "extra_profile", None)
    from autoops.config.store import ConfigStore

    store = store_secrets or ConfigStore()
    if profile is None:
        profile = store.get_profile()

    if profile is None:
        if config.llm_configured:
            return _call_azure(config, tool, user_message, max_tokens)
        raise RuntimeError("No LLM provider configured. Run: autoops setup")

    pname = profile.name
    api_key = store.get_secret(pname, "api_key")

    logger.debug("LLM router: provider=%s tool=%s", profile.provider, tool["name"])

    if profile.provider == ProviderKind.AZURE_OPENAI:
        cfg = config
        cfg.azure_openai_api_key = api_key or cfg.azure_openai_api_key
        cfg.azure_openai_endpoint = profile.endpoint or cfg.azure_openai_endpoint
        cfg.azure_openai_deployment = profile.deployment or profile.model or cfg.azure_openai_deployment
        return _call_azure(cfg, tool, user_message, max_tokens)

    if profile.provider == ProviderKind.OPENAI:
        return _call_openai_compatible(
            api_key or os.getenv("OPENAI_API_KEY", ""),
            None,
            profile.model or "gpt-4o",
            tool,
            user_message,
            max_tokens,
        )

    if profile.provider == ProviderKind.OPENROUTER:
        return _call_openai_compatible(
            api_key or os.getenv("OPENROUTER_API_KEY", ""),
            "https://openrouter.ai/api/v1",
            profile.model or "openai/gpt-4o",
            tool,
            user_message,
            max_tokens,
        )

    if profile.provider == ProviderKind.CLAUDE:
        return _call_claude(
            api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            profile.model or "claude-sonnet-4-20250514",
            tool,
            user_message,
            max_tokens,
        )

    if profile.provider == ProviderKind.BEDROCK_CLAUDE:
        return _call_bedrock(profile, tool, user_message, max_tokens)

    raise RuntimeError(f"Unsupported provider: {profile.provider}")
