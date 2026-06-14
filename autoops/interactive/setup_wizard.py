"""Interactive first-run setup wizard."""

from __future__ import annotations

import questionary
from rich.console import Console

from autoops.config.store import ConfigStore
from autoops.llm.providers import PROVIDER_LABELS, ProviderKind, ProviderProfile
from autoops.llm.router import call_with_tool
from autoops.models.config import AutoOpsConfig

console = Console()

TEST_TOOL = {
    "name": "ping",
    "description": "Health check",
    "input_schema": {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    },
}


def _prompt_provider() -> ProviderKind:
    choices = [
        questionary.Choice(title=label, value=kind.value)
        for kind, label in PROVIDER_LABELS.items()
    ]
    value = questionary.select(
        "Choose your LLM provider:",
        choices=choices,
    ).ask()
    if not value:
        raise KeyboardInterrupt("Setup cancelled")
    return ProviderKind(value)


def _prompt_secrets(kind: ProviderKind) -> dict[str, str]:
    secrets: dict[str, str] = {}
    if kind in (ProviderKind.OPENAI, ProviderKind.CLAUDE, ProviderKind.OPENROUTER, ProviderKind.AZURE_OPENAI):
        key = questionary.password("API key:").ask()
        if not key:
            raise ValueError("API key is required")
        secrets["api_key"] = key
    if kind == ProviderKind.BEDROCK_CLAUDE:
        use_profile = questionary.confirm(
            "Use AWS profile from ~/.aws/credentials?",
            default=True,
        ).ask()
        if use_profile:
            profile = questionary.text("AWS profile name:", default="default").ask()
            secrets["aws_profile"] = profile or "default"
        else:
            secrets["aws_access_key_id"] = questionary.password("AWS Access Key ID:").ask() or ""
            secrets["aws_secret_access_key"] = questionary.password("AWS Secret Access Key:").ask() or ""
    return secrets


def _prompt_profile_fields(kind: ProviderKind) -> ProviderProfile:
    name = questionary.text("Profile name:", default="default").ask() or "default"
    profile = ProviderProfile(name=name, provider=kind)

    if kind == ProviderKind.OPENAI:
        profile.model = questionary.text("Model:", default="gpt-4o").ask() or "gpt-4o"
    elif kind == ProviderKind.CLAUDE:
        profile.model = (
            questionary.text("Model:", default="claude-sonnet-4-20250514").ask()
            or "claude-sonnet-4-20250514"
        )
    elif kind == ProviderKind.OPENROUTER:
        profile.model = (
            questionary.text("Model slug:", default="openai/gpt-4o").ask() or "openai/gpt-4o"
        )
    elif kind == ProviderKind.AZURE_OPENAI:
        profile.endpoint = questionary.text(
            "Azure endpoint (https://xxx.openai.azure.com/):"
        ).ask() or ""
        profile.deployment = questionary.text("Deployment name:", default="gpt-4o").ask() or "gpt-4o"
        profile.api_version = (
            questionary.text("API version:", default="2024-10-21").ask() or "2024-10-21"
        )
    elif kind == ProviderKind.BEDROCK_CLAUDE:
        profile.region = questionary.text("AWS region:", default="us-east-1").ask() or "us-east-1"
        profile.model = (
            questionary.text(
                "Bedrock model ID:",
                default="anthropic.claude-3-5-sonnet-20241022-v2:0",
            ).ask()
            or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

    return profile


def run_setup_wizard(test: bool = True) -> ProviderProfile:
    """Run interactive setup and optionally test the provider."""
    console.print("\n[bold cyan]AutoOps Setup[/bold cyan]\n")
    store = ConfigStore()
    kind = _prompt_provider()
    profile = _prompt_profile_fields(kind)
    secrets = _prompt_secrets(kind)

    store.save_profile(profile)
    for field, value in secrets.items():
        if value:
            store.set_secret(profile.name, field, value)

    if profile.provider == ProviderKind.BEDROCK_CLAUDE and secrets.get("aws_profile"):
        profile.aws_profile = secrets["aws_profile"]
        store.save_profile(profile)

    console.print(f"\n[green]Saved profile:[/green] {profile.name} ({PROVIDER_LABELS[kind]})")

    if test:
        console.print("[dim]Testing provider connection...[/dim]")
        config = store.profile_to_autoops_config(profile)
        try:
            result = call_with_tool(
                config,
                TEST_TOOL,
                "Respond with status ok",
                profile=profile,
                store_secrets=store,
            )
            console.print(f"[green]Provider test OK:[/green] {result}")
        except Exception as exc:
            console.print(f"[yellow]Provider test failed:[/yellow] {exc}")
            console.print("You can fix credentials later with: autoops provider set")

    console.print("\n[bold]Next step:[/bold] cd into your project and run:")
    console.print("  [cyan]autoops configure --repo .[/cyan]\n")
    return profile
