"""Tests for interactive setup wizard."""

from unittest.mock import MagicMock, patch

import pytest

from autoops.interactive.setup_wizard import run_setup_wizard
from autoops.llm.providers import ProviderKind, ProviderProfile


def test_setup_wizard_openai_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOOPS_DATA_DIR", str(tmp_path))

    with patch("autoops.interactive.setup_wizard._prompt_provider", return_value=ProviderKind.OPENAI):
        with patch(
            "autoops.interactive.setup_wizard._prompt_profile_fields",
            return_value=ProviderProfile(
                name="default", provider=ProviderKind.OPENAI, model="gpt-4o"
            ),
        ):
            with patch(
                "autoops.interactive.setup_wizard._prompt_secrets",
                return_value={"api_key": "sk-test"},
            ):
                with patch("autoops.interactive.setup_wizard.call_with_tool", return_value={"status": "ok"}):
                    profile = run_setup_wizard(test=True)

    assert profile.provider == ProviderKind.OPENAI


def test_setup_wizard_requires_api_key():
    with patch("autoops.interactive.setup_wizard._prompt_provider", return_value=ProviderKind.OPENAI):
        with patch("autoops.interactive.setup_wizard._prompt_profile_fields"):
            with patch("autoops.interactive.setup_wizard._prompt_secrets", side_effect=ValueError("API key is required")):
                with pytest.raises(ValueError, match="API key"):
                    run_setup_wizard(test=False)
