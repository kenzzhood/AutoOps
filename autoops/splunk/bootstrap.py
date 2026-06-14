"""Auto-bootstrap Splunk Enterprise via Docker for zero-config init."""

from __future__ import annotations

import subprocess
import time
import uuid
import webbrowser
from dataclasses import dataclass

import requests

from autoops.models.config import AutoOpsConfig
from autoops.splunk.rest_client import SplunkRESTClient
from autoops.utils.docker import (
    DOCKER_DESKTOP_URL,
    container_exists,
    container_health,
    container_running,
    docker_platform_args,
    ensure_docker_running,
    is_arm_emulated,
    run_docker,
)
from autoops.utils.file_utils import load_json, save_json
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

CONTAINER_NAME = "autoops-splunk"
SPLUNK_IMAGE = "splunk/splunk:latest"
READINESS_TIMEOUT_SECONDS = 600 if is_arm_emulated() else 300
READINESS_POLL_INTERVAL = 5
READINESS_EXTENDED_SECONDS = 300
class DockerNotAvailableError(RuntimeError):
    """Raised when Docker is required but not installed or running."""


@dataclass
class SplunkBootstrapResult:
    already_running: bool = False
    container_started: bool = False
    hec_token: str = ""
    message: str = ""
    success: bool = True


def _splunk_admin_password(config: AutoOpsConfig) -> str:
    """Splunk blocks remote REST login with the default 'changeme' password."""
    if config.splunk_password and config.splunk_password != "changeme":
        return config.splunk_password
    state = load_json(config.state_file, default={}) or {}
    if state.get("splunk_password") and state["splunk_password"] != "changeme":
        return state["splunk_password"]
    return f"AutoOps-{uuid.uuid4().hex[:12]}!"


def _default_hec_token(config: AutoOpsConfig) -> str:
    if config.splunk_token:
        return config.splunk_token
    state = load_json(config.state_file, default={}) or {}
    if state.get("splunk_hec_token"):
        return state["splunk_hec_token"]
    return str(uuid.uuid4())


def _remove_container(name: str) -> None:
    run_docker(["rm", "-f", name], check=False)


def _start_splunk_container(config: AutoOpsConfig, hec_token: str, admin_password: str) -> bool:
    """Start or create the autoops-splunk container. Returns True if newly created."""
    platform = docker_platform_args()

    if container_running(CONTAINER_NAME):
        return False

    if container_exists(CONTAINER_NAME):
        logger.info("Starting existing Splunk container: %s", CONTAINER_NAME)
        run_docker(["start", CONTAINER_NAME], check=False)
        time.sleep(3)
        if container_running(CONTAINER_NAME):
            return False
        logger.warning("Splunk container failed to start — removing and recreating")
        _remove_container(CONTAINER_NAME)

    logger.info("Pulling Splunk image (first run may take several minutes)...")
    run_docker(["pull", *platform, SPLUNK_IMAGE])

    logger.info("Creating Splunk container: %s", CONTAINER_NAME)
    run_docker(
        [
            "run",
            "-d",
            *platform,
            "--name",
            CONTAINER_NAME,
            "-p",
            "8000:8000",
            "-p",
            "8088:8088",
            "-p",
            "8089:8089",
            "-e",
            "SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com",
            "-e",
            "SPLUNK_START_ARGS=--accept-license",
            "-e",
            f"SPLUNK_PASSWORD={admin_password}",
            "-e",
            f"SPLUNK_HEC_TOKEN={hec_token}",
            SPLUNK_IMAGE,
        ]
    )
    return True


def _wait_for_splunk(config: AutoOpsConfig) -> bool:
    """Poll Splunk REST until ready."""
    client = SplunkRESTClient(config)
    deadline = time.time() + READINESS_TIMEOUT_SECONDS
    while time.time() < deadline:
        if client.test_connection():
            return True
        time.sleep(READINESS_POLL_INTERVAL)

    if container_running(CONTAINER_NAME):
        health = container_health(CONTAINER_NAME)
        extra_deadline = time.time() + READINESS_EXTENDED_SECONDS
        while time.time() < extra_deadline:
            if client.test_connection():
                return True
            time.sleep(READINESS_POLL_INTERVAL)
    return False


def _verify_or_create_hec(config: AutoOpsConfig, hec_token: str) -> str:
    """Verify HEC is enabled; create HTTP input as fallback."""
    base = config.splunk_rest_base.rstrip("/")
    session = requests.Session()
    session.auth = (config.splunk_username, config.splunk_password)
    session.verify = False

    try:
        resp = session.get(f"{base}/services/data/inputs/http", timeout=15)
        if resp.status_code == 200:
            return hec_token
    except requests.RequestException as exc:
        logger.warning("HEC verification failed: %s", exc)

    try:
        session.post(
            f"{base}/services/data/inputs/http",
            data={
                "name": "autoops",
                "token": hec_token,
                "index": "main",
                "sourcetype": "autoops",
            },
            timeout=15,
        )
        logger.info("Created HEC input: autoops")
    except requests.RequestException as exc:
        logger.warning("Could not create HEC input (may already exist): %s", exc)

    return hec_token


def _persist_bootstrap_state(
    config: AutoOpsConfig,
    result: SplunkBootstrapResult,
) -> None:
    state = load_json(config.state_file, default={}) or {}
    state.update(
        {
            "splunk_container": CONTAINER_NAME,
            "splunk_url": config.splunk_url,
            "splunk_mcp_url": config.splunk_mcp_url,
            "splunk_hec_token": result.hec_token,
            "splunk_password": config.splunk_password,
            "splunk_bootstrapped": True,
            "splunk_bootstrap_message": result.message,
        }
    )
    save_json(config.state_file, state)


def ensure_splunk(config: AutoOpsConfig) -> SplunkBootstrapResult:
    """
    Ensure Splunk is reachable. If not, bootstrap via Docker.
    Updates config.splunk_token on success and persists to state.json.
    """
    client = SplunkRESTClient(config)
    if client.test_connection():
        token = config.splunk_token or _default_hec_token(config)
        if token:
            config.splunk_token = token
        result = SplunkBootstrapResult(
            already_running=True,
            hec_token=token,
            message="Splunk already running",
        )
        _persist_bootstrap_state(config, result)
        return result

    logger.info("Splunk not reachable — bootstrapping via Docker...")

    ok, docker_msg = ensure_docker_running()
    if not ok:
        webbrowser.open(DOCKER_DESKTOP_URL)
        return SplunkBootstrapResult(success=False, message=docker_msg)

    admin_password = _splunk_admin_password(config)
    config.splunk_password = admin_password
    hec_token = _default_hec_token(config)

    if container_exists(CONTAINER_NAME) and config.splunk_password != "changeme":
        inspect = run_docker(
            ["inspect", CONTAINER_NAME, "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
            check=False,
        )
        if "SPLUNK_PASSWORD=changeme" in (inspect.stdout or ""):
            _remove_container(CONTAINER_NAME)

    try:
        container_started = _start_splunk_container(config, hec_token, admin_password)
    except subprocess.CalledProcessError as exc:
        return SplunkBootstrapResult(
            success=False,
            message=f"Failed to start Splunk container: {exc.stderr or exc}",
        )

    if not _wait_for_splunk(config):
        logs = run_docker(["logs", "--tail", "20", CONTAINER_NAME], check=False)
        return SplunkBootstrapResult(
            success=False,
            container_started=container_started,
            message=(
                f"Splunk container started but did not become ready within "
                f"{READINESS_TIMEOUT_SECONDS}s. Check: docker logs {CONTAINER_NAME}"
            ),
        )

    hec_token = _verify_or_create_hec(config, hec_token)
    config.splunk_token = hec_token

    result = SplunkBootstrapResult(
        already_running=False,
        container_started=container_started or True,
        hec_token=hec_token,
        message="Splunk bootstrapped via Docker",
        success=True,
    )
    _persist_bootstrap_state(config, result)
    logger.info("Splunk bootstrap complete — UI at %s", config.splunk_url)
    return result
