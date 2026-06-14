"""autoops telemetry — OpenTelemetry Collector."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from autoops.models.config import AutoOpsConfig
from autoops.telemetry.collector import (
    COLLECTOR_CONTAINER,
    ensure_collector,
    send_test_event,
)
from autoops.utils.docker import run_docker

console = Console()
app = typer.Typer(help="Manage OpenTelemetry Collector")


@app.command("start")
def start(repo: str = typer.Option(".", "--repo")):
    config = AutoOpsConfig.from_env()
    result = ensure_collector(config, Path(repo).resolve())
    if result.success:
        console.print(f"[green]{result.message}[/green]")
        console.print(f"Config: {result.config_path}")
    else:
        console.print(f"[red]{result.message}[/red]")
        raise typer.Exit(1)


@app.command("status")
def status():
    from autoops.utils.docker import container_running

    running = container_running(COLLECTOR_CONTAINER)
    console.print(f"Collector: {'running' if running else 'stopped'}")


@app.command("stop")
def stop():
    run_docker(["stop", COLLECTOR_CONTAINER], check=False)
    console.print("Collector stopped")


@app.command("test")
def test():
    config = AutoOpsConfig.from_env()
    ok = send_test_event(config)
    if ok:
        console.print("[green]Synthetic HEC event sent successfully[/green]")
        console.print("SPL: index=main sourcetype=autoops:event message=\"autoops synthetic test event\"")
    else:
        console.print("[red]HEC test failed — ensure Splunk is running[/red]")
        raise typer.Exit(1)
