"""AutoOps AI CLI — product command surface."""

from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from autoops.agents.instrumentation import generate_instrumentation
from autoops.agents.orchestrator import run_configure_pipeline, run_investigation_pipeline
from autoops.agents.splunk_config import configure_splunk
from autoops.commands import demo_cmds, doctor, provider, splunk_cmds, telemetry_cmds
from autoops.config.store import ConfigStore
from autoops.interactive.setup_wizard import run_setup_wizard
from autoops.models.config import AutoOpsConfig
from autoops.scanner.repo_scanner import scan_repository
from autoops.utils.file_utils import load_json, save_json
from autoops.utils.logger import setup_logging

app = typer.Typer(name="autoops", help="Autonomous observability for any codebase")
console = Console()

app.add_typer(provider.app, name="provider")
app.add_typer(splunk_cmds.app, name="splunk")
app.add_typer(telemetry_cmds.app, name="telemetry")
app.add_typer(demo_cmds.app, name="demo")
app.add_typer(doctor.app, name="doctor")


def _run_async(coro):
    return asyncio.run(coro)


def _print_configure_result(result, config: AutoOpsConfig) -> None:
    arch = result.architecture
    console.print(
        f"[green]Discovered[/green] {len(arch.services)} services, "
        f"{len(arch.databases)} databases, {len(arch.critical_paths)} critical paths"
    )
    if result.instrumentation_files:
        console.print("\n[bold]Instrumentation[/bold]")
        for f in result.instrumentation_files:
            console.print(f"  Written: [cyan]{f}[/cyan]")
    if result.splunk_bootstrap:
        if result.splunk_bootstrap.success and result.splunk_bootstrap.container_started:
            console.print("\n[bold]Splunk[/bold] started via Docker")
        elif result.splunk_bootstrap.already_running:
            console.print("\n[bold]Splunk[/bold] already running")
        elif not result.splunk_bootstrap.success:
            console.print(f"\n[yellow]Splunk:[/yellow] {result.splunk_bootstrap.message}")
    if result.collector and result.collector.success:
        console.print(f"[bold]OTel Collector[/bold] {result.collector.message}")
    if result.splunk:
        console.print("\n[bold]Splunk config[/bold]")
        for dash in result.splunk.dashboards_created:
            console.print(f"  Dashboard: [green]{dash}[/green]")
        console.print(f"  Alerts: [green]{len(result.splunk.alerts_created)}[/green]")
        console.print(f"  Saved searches: [green]{len(result.splunk.saved_searches_created)}[/green]")
    if result.synthetic_test_ok:
        console.print("\n[green]Synthetic telemetry test passed[/green]")
    if result.next_commands:
        console.print("\n[bold]Next commands[/bold]")
        for cmd in result.next_commands:
            console.print(f"  [cyan]{cmd}[/cyan]")
    console.print(
        f"\n[bold green]Done![/bold green] Monitoring [cyan]{arch.app_name}[/cyan]"
    )
    console.print(f"Splunk: {config.splunk_url}/en-US/app/search/dashboards\n")


@app.command()
def setup():
    """Interactive global setup — choose LLM provider and save credentials."""
    setup_logging()
    run_setup_wizard(test=True)


@app.command()
def configure(
    repo: str = typer.Option(".", "--repo", help="Git repo URL or local path"),
    profile: str = typer.Option("default", "--profile"),
    splunk_url: str = typer.Option("http://localhost:8000", "--splunk-url"),
    no_instrument: bool = typer.Option(False, "--no-instrument"),
    no_splunk_setup: bool = typer.Option(False, "--no-splunk-setup"),
    no_collector: bool = typer.Option(False, "--no-collector"),
):
    """Configure observability for a project (Splunk + telemetry + instrumentation)."""
    setup_logging()
    store = ConfigStore()
    if not store.get_profile():
        console.print("[yellow]No LLM profile — starting setup wizard...[/yellow]")
        run_setup_wizard(test=False)

    config = store.profile_to_autoops_config(store.get_profile(profile))
    config.splunk_url = splunk_url

    console.print("\n[bold cyan]AutoOps Configure[/bold cyan]\n")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Bootstrapping Splunk and scanning repo...", total=None)
        result = _run_async(
            run_configure_pipeline(
                repo,
                config,
                profile_name=profile,
                no_instrument=no_instrument,
                setup_splunk=not no_splunk_setup,
                setup_collector=not no_collector,
            )
        )
        progress.update(task, description="Complete")
    _print_configure_result(result, config)


@app.command()
def init(
    repo: str = typer.Option(..., "--repo"),
    splunk_url: str = typer.Option("http://localhost:8000", "--splunk-url"),
    no_instrument: bool = typer.Option(False, "--no-instrument"),
    no_splunk_setup: bool = typer.Option(False, "--no-splunk-setup"),
):
    """Alias for configure (backward compatible)."""
    configure(
        repo=repo,
        profile="default",
        splunk_url=splunk_url,
        no_instrument=no_instrument,
        no_splunk_setup=no_splunk_setup,
        no_collector=False,
    )


@app.command()
def scan(
    repo: str = typer.Option(".", "--repo"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
):
    setup_logging()
    scan_result = scan_repository(repo)
    summary = {
        "root": str(scan_result.root),
        "file_count": len(scan_result.file_tree),
        "file_tree": scan_result.file_tree[:100],
        "key_files": list(scan_result.key_files.keys()),
    }
    if output:
        from pathlib import Path

        save_json(Path(output), summary)
        console.print(f"[green]Saved to {output}[/green]")
    else:
        console.print(json.dumps(summary, indent=2))


@app.command()
def instrument(
    repo: str = typer.Option(".", "--repo"),
):
    """Generate instrumentation files only."""
    setup_logging()
    store = ConfigStore()
    config = store.profile_to_autoops_config(store.get_profile())
    scan = scan_repository(repo)
    arch_data = load_json(config.architecture_file)
    if not arch_data:
        console.print("[red]No architecture map. Run autoops configure first.[/red]")
        raise typer.Exit(1)
    from autoops.models.architecture import ArchitectureMap

    arch = ArchitectureMap.model_validate(arch_data)
    files = generate_instrumentation(arch, scan.root, config)
    for f in files:
        console.print(f"  [cyan]{f}[/cyan]")


dashboards_app = typer.Typer(help="Splunk dashboards")
alerts_app = typer.Typer(help="Splunk alerts")
app.add_typer(dashboards_app, name="dashboards")
app.add_typer(alerts_app, name="alerts")


@dashboards_app.command("apply")
def dashboards_apply(repo: str = typer.Option(".", "--repo")):
    config = AutoOpsConfig.from_env()
    arch_data = load_json(config.architecture_file)
    if not arch_data:
        console.print("[red]Run autoops configure first[/red]")
        raise typer.Exit(1)
    from autoops.models.architecture import ArchitectureMap

    result = configure_splunk(ArchitectureMap.model_validate(arch_data), config)
    console.print(f"Created {len(result.dashboards_created)} dashboards")


@dashboards_app.command("list")
def dashboards_list():
    state = load_json(AutoOpsConfig.from_env().state_file, default={}) or {}
    for d in state.get("dashboards", []):
        console.print(f"  {d}")


@dashboards_app.command("open")
def dashboards_open():
    splunk_cmds.open_ui()


@alerts_app.command("apply")
def alerts_apply():
    dashboards_apply()


@alerts_app.command("list")
def alerts_list():
    state = load_json(AutoOpsConfig.from_env().state_file, default={}) or {}
    for a in state.get("alerts", []):
        console.print(f"  {a}")


@alerts_app.command("test")
def alerts_test():
    telemetry_cmds.test()


@app.command()
def investigate(
    alert_name: str = typer.Option(..., "--alert"),
    window: str = typer.Option("30m", "--window"),
    services: Optional[str] = typer.Option(None, "--services"),
):
    setup_logging()
    store = ConfigStore()
    config = store.profile_to_autoops_config(store.get_profile())
    affected = [s.strip() for s in services.split(",")] if services else None
    console.print(f"\n[bold cyan]Investigating:[/bold cyan] {alert_name}\n")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Running investigation...", total=None)
        result = _run_async(run_investigation_pipeline(alert_name, affected, window, config))
        progress.update(task, description="Done")
    incident = result.incident
    console.print(Panel(incident.executive_summary, title="Executive Summary", border_style="red"))
    table = Table(title="Root Causes")
    table.add_column("Component")
    table.add_column("Hypothesis")
    table.add_column("Confidence")
    for rc in incident.root_causes:
        table.add_row(rc.component, rc.hypothesis, f"{rc.confidence:.0%}")
    console.print(table)
    console.print(f"\n[green]Completed in {result.duration_seconds:.1f}s[/green]")


@app.command()
def watch(webhook_port: int = typer.Option(9000, "--port")):
    setup_logging()
    store = ConfigStore()
    config = store.profile_to_autoops_config(store.get_profile())

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path not in ("/webhook", "/"):
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}
            alert_name = payload.get("alert_name") or payload.get("search_name") or "unknown_alert"
            services = payload.get("affected_services", [])
            result = _run_async(
                run_investigation_pipeline(alert_name, services or None, "30m", config)
            )
            console.print(f"[green]Investigation:[/green] {result.incident.executive_summary}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(result.incident.model_dump_json().encode())

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("0.0.0.0", webhook_port), WebhookHandler)
    console.print(f"[cyan]Watching on port {webhook_port}[/cyan] — POST /webhook")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("[yellow]Stopped[/yellow]")


if __name__ == "__main__":
    app()
