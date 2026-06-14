"""Cross-platform Docker detection and helpers."""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
import webbrowser
from typing import Callable

DOCKER_DESKTOP_URL = "https://www.docker.com/products/docker-desktop/"

DOCKER_START_TIMEOUT = 90


def docker_binary() -> str | None:
    return shutil.which("docker")


def docker_daemon_running() -> bool:
    if not docker_binary():
        return False
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    except OSError:
        return False


def open_docker_download_page() -> None:
    webbrowser.open(DOCKER_DESKTOP_URL)


def _try_start_macos() -> bool:
    try:
        subprocess.Popen(
            ["open", "-a", "Docker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    deadline = time.time() + DOCKER_START_TIMEOUT
    while time.time() < deadline:
        if docker_daemon_running():
            return True
        time.sleep(2)
    return False


def _try_start_windows() -> bool:
    try:
        subprocess.Popen(
            [
                "powershell",
                "-Command",
                "Start-Process 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    deadline = time.time() + DOCKER_START_TIMEOUT
    while time.time() < deadline:
        if docker_daemon_running():
            return True
        time.sleep(2)
    return False


def ensure_docker_running() -> tuple[bool, str]:
    """
    Ensure Docker is available. Returns (success, message).
    Does not silently install Docker.
    """
    if not docker_binary():
        open_docker_download_page()
        return False, (
            "Docker is not installed. Install Docker Desktop, then re-run.\n"
            f"Download: {DOCKER_DESKTOP_URL}"
        )
    if docker_daemon_running():
        return True, "Docker is running"

    system = platform.system()
    if system == "Darwin":
        if _try_start_macos():
            return True, "Started Docker Desktop"
    elif system == "Windows":
        if _try_start_windows():
            return True, "Started Docker Desktop"

    return False, (
        "Docker is installed but not running. Start Docker Desktop, then re-run."
    )


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if port is in use (something listening)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def check_ports(ports: list[int]) -> dict[int, bool]:
    return {p: check_port(p) for p in ports}


def docker_platform_args() -> list[str]:
    """Use amd64 emulation on Apple Silicon where images lack arm64 manifests."""
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return ["--platform", "linux/amd64"]
    return []


def run_docker(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *cmd],
        capture_output=True,
        text=True,
        check=check,
    )


def container_exists(name: str) -> bool:
    r = run_docker(
        ["ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        check=False,
    )
    return name in (r.stdout or "").strip().splitlines()


def container_running(name: str) -> bool:
    r = run_docker(
        ["ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        check=False,
    )
    return name in (r.stdout or "").strip().splitlines()


def container_health(name: str) -> str:
    """Return Docker health status: healthy, starting, unhealthy, or unknown."""
    r = run_docker(
        ["inspect", name, "--format", "{{.State.Health.Status}}"],
        check=False,
    )
    return (r.stdout or "").strip() or "unknown"


def is_arm_emulated() -> bool:
    return platform.machine().lower() in ("arm64", "aarch64")
