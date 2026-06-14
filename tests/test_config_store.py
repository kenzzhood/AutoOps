"""Tests for config store."""

from autoops.config.store import ConfigStore
from autoops.llm.providers import ProviderKind, ProviderProfile


def test_save_and_load_profile(tmp_path):
    store = ConfigStore(tmp_path)
    profile = ProviderProfile(name="default", provider=ProviderKind.OPENAI, model="gpt-4o")
    store.save_profile(profile)
    store.set_secret("default", "api_key", "sk-test")
    loaded = store.get_profile("default")
    assert loaded is not None
    assert loaded.provider == ProviderKind.OPENAI
    assert store.get_secret("default", "api_key") == "sk-test"


def test_secrets_fallback_without_keyring(tmp_path, monkeypatch):
    monkeypatch.setattr("autoops.config.store._keyring_available", lambda: False)
    store = ConfigStore(tmp_path)
    store.set_secret("default", "api_key", "fallback-key")
    assert store.get_secret("default", "api_key") == "fallback-key"
