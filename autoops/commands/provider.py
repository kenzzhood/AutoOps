"""autoops provider — manage LLM profiles."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from autoops.config.store import ConfigStore
from autoops.interactive.setup_wizard import run_setup_wizard
from autoops.llm.providers import PROVIDER_LABELS
from autoops.llm.router import call_with_tool

console = Console()
app = typer.Typer(help="Manage LLM provider profiles")

TEST_TOOL = {
    "name": "ping",
    "description": "Health check",
    "input_schema": {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    },
}


@app.command("list")
def list_profiles():
    store = ConfigStore()
    names = store.list_profiles()
    active = store.get_active_profile_name()
    if not names:
        console.print("[yellow]No profiles. Run:[/yellow] autoops setup")
        return
    for n in names:
        mark = " (active)" if n == active else ""
        p = store.get_profile(n)
        label = PROVIDER_LABELS.get(p.provider, p.provider.value) if p else ""
        console.print(f"  {n}{mark} — {label}")


@app.command("show")
def show_profile(name: str = typer.Option(None, "--name")):
    store = ConfigStore()
    profile = store.get_profile(name)
    if not profile:
        console.print("[red]Profile not found[/red]")
        raise typer.Exit(1)
    console.print(profile.model_dump_json(indent=2))


@app.command("set")
def set_profile():
    run_setup_wizard(test=True)


@app.command("test")
def test_profile(name: str = typer.Option(None, "--name")):
    store = ConfigStore()
    profile = store.get_profile(name)
    if not profile:
        console.print("[red]No profile configured[/red]")
        raise typer.Exit(1)
    config = store.profile_to_autoops_config(profile)
    result = call_with_tool(
        config, TEST_TOOL, "Respond with status ok", profile=profile, store_secrets=store
    )
    console.print(f"[green]OK:[/green] {result}")
