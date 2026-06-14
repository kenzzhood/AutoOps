"""LLM provider types and profile models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderKind(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"
    BEDROCK_CLAUDE = "bedrock_claude"


PROVIDER_LABELS = {
    ProviderKind.OPENAI: "OpenAI",
    ProviderKind.CLAUDE: "Claude (Anthropic)",
    ProviderKind.OPENROUTER: "OpenRouter",
    ProviderKind.AZURE_OPENAI: "Azure OpenAI",
    ProviderKind.BEDROCK_CLAUDE: "Amazon Bedrock (Claude)",
}


class ProviderProfile(BaseModel):
    """Non-secret provider configuration."""

    name: str = "default"
    provider: ProviderKind = ProviderKind.AZURE_OPENAI
    model: str = ""
    deployment: str = ""
    endpoint: str = ""
    api_version: str = "2024-10-21"
    region: str = "us-east-1"
    aws_profile: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    def display_model(self) -> str:
        if self.provider == ProviderKind.AZURE_OPENAI:
            return self.deployment or self.model or "gpt-4o"
        return self.model or "default"
