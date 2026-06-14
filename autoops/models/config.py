from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autoops.utils.file_utils import expand_path, load_json


class AutoOpsConfig(BaseModel):
    """Runtime configuration loaded from environment."""

    azure_openai_api_key: str = Field(default="")
    azure_openai_endpoint: str = Field(default="")
    azure_openai_deployment: str = Field(default="")
    azure_openai_api_version: str = Field(default="2024-10-21")
    splunk_url: str = Field(default="http://localhost:8000")
    splunk_username: str = Field(default="admin")
    splunk_password: str = Field(default="changeme")
    splunk_token: str = Field(default="")
    splunk_mcp_url: str = Field(default="http://localhost:8089")
    data_dir: Path = Field(default_factory=lambda: expand_path("~/.autoops"))
    extra_profile: Any = Field(default=None, exclude=True)

    @classmethod
    def from_env(cls) -> AutoOpsConfig:
        data_dir = expand_path(os.getenv("AUTOOPS_DATA_DIR", "~/.autoops"))
        state = load_json(data_dir / "state.json", default={}) or {}

        splunk_token = os.getenv("SPLUNK_TOKEN", "") or state.get("splunk_hec_token", "")
        splunk_password = os.getenv("SPLUNK_PASSWORD", "") or state.get("splunk_password", "changeme")
        splunk_url = os.getenv("SPLUNK_URL", state.get("splunk_url", "http://localhost:8000"))
        splunk_mcp_url = os.getenv(
            "SPLUNK_MCP_URL", state.get("splunk_mcp_url", "http://localhost:8089")
        )

        return cls(
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_deployment=os.getenv(
                "AZURE_OPENAI_DEPLOYMENT",
                os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
            ),
            azure_openai_api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION", "2024-10-21"
            ),
            splunk_url=splunk_url,
            splunk_username=os.getenv("SPLUNK_USERNAME", "admin"),
            splunk_password=splunk_password,
            splunk_token=splunk_token,
            splunk_mcp_url=splunk_mcp_url,
            data_dir=data_dir,
        )

    @property
    def llm_configured(self) -> bool:
        """True when an LLM provider or legacy Azure env vars are present."""
        from autoops.config.store import ConfigStore

        if ConfigStore(self.data_dir).get_profile():
            return True
        return bool(
            self.azure_openai_api_key
            and self.azure_openai_endpoint
            and self.azure_openai_deployment
        )

    @property
    def splunk_rest_base(self) -> str:
        """Management port REST base URL (Splunk serves REST over HTTPS on 8089)."""
        url = self.splunk_url.rstrip("/")
        if ":8000" in url:
            host = url.split("://", 1)[-1].replace(":8000", "")
            return f"https://{host}:8089"
        base = self.splunk_mcp_url.rstrip("/")
        if base.startswith("http://"):
            return "https://" + base[len("http://") :]
        return base

    @property
    def mcp_endpoint(self) -> str:
        base = self.splunk_mcp_url.rstrip("/")
        if base.endswith("/services/mcp"):
            return base
        return f"{base}/services/mcp"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def architecture_file(self) -> Path:
        return self.data_dir / "architecture.json"
