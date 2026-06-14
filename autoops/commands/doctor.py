"""autoops doctor — environment checks."""

from __future__ import annotations

import shutil
import sys

import typer
from rich.console import Console
from rich.table import Table

from autoops.config.store import ConfigStore
from autoops.models.config import AutoOpsConfig
from autoops.splunk.bootstrap import CONTAINER_NAME as SPLUNK_CONTAINER
from autoops.splunk.rest_client import SplunkRESTClient
from autoops.telemetry.collector import COLLECTOR_CONTAINER, send_test_event
from autoops.utils.docker import check_ports, container_running, docker_daemon_running

console = Console()
app = typer.Typer(help="Validate AutoOps environment")


@app.callback(invoke_without_command=True)
def doctor():
    """Run all health checks."""
    table = Table(title="AutoOps Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    py_ok = sys.version_info >= (3, 11)
    table.add_row("Python 3.11+", "OK" if py_ok else "FAIL", f"{sys.version_info.major}.{sys.version_info.minor}")

    docker_ok = docker_daemon_running()
    table.add_row("Docker", "OK" if docker_ok else "FAIL", "daemon running" if docker_ok else "not running")

    ports = check_ports([8000, 8088, 8089, 4317, 4318])
    for port, in_use in ports.items():
        table.add_row(f"Port {port}", "IN USE" if in_use else "free", "")

    store = ConfigStore()
    profile = store.get_profile()
    table.add_row("LLM profile", "OK" if profile else "MISSING", profile.provider.value if profile else "run autoops setup")

    config = AutoOpsConfig.from_env()
    if profile:
        config = store.profile_to_autoops_config(profile)
    splunk = SplunkRESTClient(config).test_connection()
    table.add_row("Splunk REST", "OK" if splunk else "FAIL", config.splunk_rest_base)

    table.add_row("Splunk container", "running" if container_running(SPLUNK_CONTAINER) else "stopped", SPLUNK_CONTAINER)
    table.add_row("OTel collector", "running" if container_running(COLLECTOR_CONTAINER) else "stopped", COLLECTOR_CONTAINER)

    hec_ok = send_test_event(config) if config.splunk_token else False
    table.add_row("HEC test", "OK" if hec_ok else "SKIP/FAIL", "token set" if config.splunk_token else "no token")

    git_ok = shutil.which("git") is not None
    table.add_row("git", "OK" if git_ok else "WARN", "")

    console.print(table)
