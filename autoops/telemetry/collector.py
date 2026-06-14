"""OpenTelemetry Collector bootstrap for AutoOps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from autoops.models.config import AutoOpsConfig
from autoops.utils.docker import (
    container_exists,
    container_running,
    docker_platform_args,
    ensure_docker_running,
    run_docker,
)
from autoops.utils.file_utils import write_file
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

COLLECTOR_CONTAINER = "autoops-otel-collector"
COLLECTOR_IMAGE = "otel/opentelemetry-collector-contrib:latest"


@dataclass
class CollectorBootstrapResult:
    success: bool = True
    config_path: str = ""
    message: str = ""


def build_collector_config(hec_token: str, splunk_hec_host: str = "host.docker.internal") -> str:
    return f"""receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:

exporters:
  splunk_hec:
    token: "{hec_token}"
    endpoint: "https://{splunk_hec_host}:8088/services/collector"
    sourcetype: "autoops:otel"
    index: "main"
    tls:
      insecure_skip_verify: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [splunk_hec]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [splunk_hec]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [splunk_hec]
"""


def write_collector_config(repo_root: Path, hec_token: str) -> Path:
    config_dir = repo_root / ".autoops"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "otel-collector-config.yaml"
    write_file(path, build_collector_config(hec_token))
    return path


def ensure_collector(config: AutoOpsConfig, repo_root: Path) -> CollectorBootstrapResult:
    ok, msg = ensure_docker_running()
    if not ok:
        return CollectorBootstrapResult(success=False, message=msg)

    hec_token = config.splunk_token
    if not hec_token:
        return CollectorBootstrapResult(success=False, message="No HEC token — run Splunk bootstrap first")

    config_path = write_collector_config(repo_root, hec_token)

    if container_running(COLLECTOR_CONTAINER):
        return CollectorBootstrapResult(
            success=True,
            config_path=str(config_path),
            message="Collector already running",
        )

    if container_exists(COLLECTOR_CONTAINER):
        run_docker(["start", COLLECTOR_CONTAINER])
        return CollectorBootstrapResult(
            success=True,
            config_path=str(config_path),
            message="Started existing collector",
        )

    platform = docker_platform_args()
    run_docker(["pull", *platform, COLLECTOR_IMAGE])
    run_docker(
        [
            "run",
            "-d",
            *platform,
            "--name",
            COLLECTOR_CONTAINER,
            "-p",
            "4317:4317",
            "-p",
            "4318:4318",
            "-v",
            f"{config_path.resolve()}:/etc/otelcol-contrib/config.yaml",
            COLLECTOR_IMAGE,
        ]
    )
    logger.info("Started OTel collector: %s", COLLECTOR_CONTAINER)
    return CollectorBootstrapResult(
        success=True,
        config_path=str(config_path),
        message="Collector started",
    )


def send_test_event(config: AutoOpsConfig) -> bool:
    """Send synthetic HEC event to verify ingestion."""
    if not config.splunk_token:
        return False
    url = "https://localhost:8088/services/collector/event"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Splunk {config.splunk_token}"},
            json={
                "event": {
                    "message": "autoops synthetic test event",
                    "level": "INFO",
                    "service": "autoops-test",
                    "sourcetype": "autoops:event",
                },
                "sourcetype": "autoops:event",
                "index": "main",
            },
            timeout=10,
            verify=False,
        )
        return resp.status_code in (200, 201)
    except requests.RequestException as exc:
        logger.warning("Synthetic HEC test failed: %s", exc)
        return False
