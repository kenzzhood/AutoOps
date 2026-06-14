"""autoops splunk — manage Splunk container."""

from __future__ import annotations

import webbrowser

import typer
from rich.console import Console

from autoops.models.config import AutoOpsConfig
from autoops.splunk.bootstrap import CONTAINER_NAME, ensure_splunk
from autoops.splunk.rest_client import SplunkRESTClient
from autoops.utils.docker import run_docker

console = Console()
app = typer.Typer(help="Manage Splunk Enterprise")


@app.command("start")
def start():
    config = AutoOpsConfig.from_env()
    result = ensure_splunk(config)
    if result.success:
        console.print(f"[green]{result.message}[/green]")
    else:
        console.print(f"[red]{result.message}[/red]")
        raise typer.Exit(1)


@app.command("status")
def status():
    config = AutoOpsConfig.from_env()
    ok = SplunkRESTClient(config).test_connection()
    console.print(f"Splunk REST: {'OK' if ok else 'DOWN'}")
    console.print(f"URL: {config.splunk_url}")


@app.command("stop")
def stop():
    run_docker(["stop", CONTAINER_NAME], check=False)
    console.print(f"Stopped {CONTAINER_NAME}")


@app.command("logs")
def logs(follow: bool = typer.Option(False, "-f")):
    cmd = ["logs", CONTAINER_NAME]
    if follow:
        cmd.insert(1, "-f")
    import subprocess

    subprocess.run(["docker", *cmd])


@app.command("reset")
def reset():
    run_docker(["rm", "-f", CONTAINER_NAME], check=False)
    console.print(f"Removed {CONTAINER_NAME}. Run autoops splunk start to recreate.")


@app.command("open")
def open_ui():
    config = AutoOpsConfig.from_env()
    webbrowser.open(f"{config.splunk_url}/en-US/app/search/dashboards")
