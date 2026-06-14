"""Global config store with keyring-backed secrets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from autoops.llm.providers import ProviderKind, ProviderProfile
from autoops.models.config import AutoOpsConfig
from autoops.utils.file_utils import ensure_data_dir, load_json, save_json

SERVICE_NAME = "autoops-ai"
DEFAULT_PROFILE = "default"


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


class ConfigStore:
    """Persist profiles in ~/.autoops/config.json and secrets in OS keychain."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or ensure_data_dir()
        self.config_path = self.data_dir / "config.json"

    def load(self) -> dict[str, Any]:
        return load_json(self.config_path, default={}) or {}

    def save(self, data: dict[str, Any]) -> None:
        save_json(self.config_path, data)

    def _secret_key(self, profile_name: str, field: str) -> str:
        return f"{profile_name}:{field}"

    def set_secret(self, profile_name: str, field: str, value: str) -> None:
        if _keyring_available():
            import keyring

            keyring.set_password(SERVICE_NAME, self._secret_key(profile_name, field), value)
            return
        # Fallback: store in config (less secure, documented)
        data = self.load()
        secrets = data.setdefault("secrets_fallback", {})
        secrets[self._secret_key(profile_name, field)] = value
        self.save(data)

    def get_secret(self, profile_name: str, field: str) -> str:
        if _keyring_available():
            import keyring

            val = keyring.get_password(SERVICE_NAME, self._secret_key(profile_name, field))
            if val:
                return val
        data = self.load()
        return (data.get("secrets_fallback") or {}).get(
            self._secret_key(profile_name, field), ""
        )

    def get_active_profile_name(self) -> str:
        return self.load().get("active_profile", DEFAULT_PROFILE)

    def set_active_profile(self, name: str) -> None:
        data = self.load()
        data["active_profile"] = name
        self.save(data)

    def save_profile(self, profile: ProviderProfile) -> None:
        data = self.load()
        profiles = data.setdefault("profiles", {})
        profiles[profile.name] = profile.model_dump()
        data["active_profile"] = profile.name
        self.save(data)

    def get_profile(self, name: str | None = None) -> ProviderProfile | None:
        data = self.load()
        pname = name or data.get("active_profile", DEFAULT_PROFILE)
        raw = (data.get("profiles") or {}).get(pname)
        if not raw:
            return None
        return ProviderProfile.model_validate(raw)

    def list_profiles(self) -> list[str]:
        return list((self.load().get("profiles") or {}).keys())

    def profile_to_autoops_config(
        self, profile: ProviderProfile | None = None
    ) -> AutoOpsConfig:
        """Merge provider profile secrets into AutoOpsConfig for agents."""
        base = AutoOpsConfig.from_env()
        profile = profile or self.get_profile()
        if not profile:
            return base

        pname = profile.name
        api_key = self.get_secret(pname, "api_key")
        aws_key = self.get_secret(pname, "aws_access_key_id")
        aws_secret = self.get_secret(pname, "aws_secret_access_key")

        if profile.provider == ProviderKind.OPENAI:
            base.azure_openai_api_key = ""  # clear azure
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
        elif profile.provider == ProviderKind.CLAUDE:
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
        elif profile.provider == ProviderKind.OPENROUTER:
            if api_key:
                os.environ["OPENROUTER_API_KEY"] = api_key
        elif profile.provider == ProviderKind.AZURE_OPENAI:
            base.azure_openai_api_key = api_key
            base.azure_openai_endpoint = profile.endpoint
            base.azure_openai_deployment = profile.deployment or profile.model
            base.azure_openai_api_version = profile.api_version
        elif profile.provider == ProviderKind.BEDROCK_CLAUDE:
            if aws_key:
                os.environ["AWS_ACCESS_KEY_ID"] = aws_key
            if aws_secret:
                os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret
            if profile.region:
                os.environ["AWS_DEFAULT_REGION"] = profile.region
            if profile.aws_profile:
                os.environ["AWS_PROFILE"] = profile.aws_profile

        base.extra_profile = profile  # type: ignore[attr-defined]
        return base


def load_active_profile() -> tuple[ProviderProfile | None, ConfigStore]:
    store = ConfigStore()
    return store.get_profile(), store
