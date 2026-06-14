#!/usr/bin/env python3
"""Seed ~/.autoops provider profile from repo .env (non-interactive, for demos/CI)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from autoops.config.store import ConfigStore
from autoops.llm.providers import ProviderKind, ProviderProfile


def main() -> int:
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "") or os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_NAME", ""
    )
    if not (api_key and endpoint and deployment):
        print(
            "Missing AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, or AZURE_OPENAI_DEPLOYMENT in .env",
            file=sys.stderr,
        )
        return 1

    profile = ProviderProfile(
        name="default",
        provider=ProviderKind.AZURE_OPENAI,
        endpoint=endpoint,
        deployment=deployment,
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )
    store = ConfigStore()
    store.save_profile(profile)
    store.set_secret("default", "api_key", api_key)
    print(f"Seeded profile '{profile.name}' ({profile.provider.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
