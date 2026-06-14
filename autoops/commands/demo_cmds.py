"""autoops demo — local demo workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Demo app workflow")

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo-app"


@app.command("start")
def start():
    subprocess.run(["docker", "compose", "up", "-d"], cwd=DEMO_DIR, check=False)
    console.print("[green]Demo stack starting[/green] (Postgres + demo-app)")
    console.print("  uvicorn main:app --reload --port 8080  (from demo-app/)")


@app.command("bug-on")
def bug_on():
    import httpx

    r = httpx.post("http://localhost:8080/admin/toggle-bug", params={"enabled": True})
    console.print(r.json())


@app.command("bug-off")
def bug_off():
    import httpx

    r = httpx.post("http://localhost:8080/admin/toggle-bug", params={"enabled": False})
    console.print(r.json())


@app.command("traffic")
def traffic(requests: int = typer.Option(30, "--requests")):
    subprocess.run(
        ["python3", "inject_bug.py", "--requests", str(requests)],
        cwd=DEMO_DIR,
        check=False,
    )
