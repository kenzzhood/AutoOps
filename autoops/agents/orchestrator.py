"""Orchestrator — runs agent pipelines in sequence."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from autoops.agents.discovery import run_discovery
from autoops.agents.evidence import collect_evidence
from autoops.agents.instrumentation import generate_instrumentation
from autoops.agents.rca import run_rca
from autoops.agents.remediation import run_remediation
from autoops.agents.splunk_config import SplunkConfigResult, configure_splunk
from autoops.models.architecture import ArchitectureMap, TechStack
from autoops.models.config import AutoOpsConfig
from autoops.models.incident import Incident
from autoops.scanner.repo_scanner import scan_repository
from autoops.config.store import ConfigStore
from autoops.splunk.bootstrap import SplunkBootstrapResult, ensure_splunk
from autoops.telemetry.collector import CollectorBootstrapResult, ensure_collector, send_test_event
from autoops.utils.file_utils import load_json, save_json
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SetupResult:
    architecture: ArchitectureMap
    instrumentation_files: list[str] = field(default_factory=list)
    splunk: SplunkConfigResult | None = None
    splunk_bootstrap: SplunkBootstrapResult | None = None
    collector: CollectorBootstrapResult | None = None
    synthetic_test_ok: bool = False
    repo_root: Path | None = None
    next_commands: list[str] = field(default_factory=list)


@dataclass
class InvestigationResult:
    incident: Incident
    duration_seconds: float


def _load_config_with_profile(config: AutoOpsConfig | None, profile_name: str | None) -> AutoOpsConfig:
    store = ConfigStore()
    profile = store.get_profile(profile_name) if profile_name else store.get_profile()
    if profile:
        return store.profile_to_autoops_config(profile)
    return config or AutoOpsConfig.from_env()


async def run_configure_pipeline(
    repo: str,
    config: AutoOpsConfig | None = None,
    profile_name: str | None = None,
    no_instrument: bool = False,
    setup_splunk: bool = True,
    setup_collector: bool = True,
) -> SetupResult:
    """Full configure pipeline for any project folder."""
    config = _load_config_with_profile(config, profile_name)
    config.data_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_repository(repo)

    bootstrap_result: SplunkBootstrapResult | None = None
    if setup_splunk:
        bootstrap_result = ensure_splunk(config)
        if not bootstrap_result.success:
            logger.warning("Splunk bootstrap: %s", bootstrap_result.message)

    collector_result: CollectorBootstrapResult | None = None
    if setup_collector and config.splunk_token:
        collector_result = ensure_collector(config, scan.root)
        if not collector_result.success:
            logger.warning("Collector bootstrap: %s", collector_result.message)

    architecture = await run_discovery(repo, config)
    save_json(config.architecture_file, architecture.model_dump())

    instrumentation_files: list[str] = []
    if not no_instrument:
        instrumentation_files = generate_instrumentation(architecture, scan.root, config)

    splunk_result = configure_splunk(architecture, config)
    synthetic_ok = send_test_event(config) if config.splunk_token else False

    state = load_json(config.state_file, default={}) or {}
    state.update(
        {
            "app_name": architecture.app_name,
            "repo": repo,
            "dashboards": splunk_result.dashboards_created,
            "alerts": splunk_result.alerts_created,
            "saved_searches": splunk_result.saved_searches_created,
        }
    )
    if bootstrap_result and bootstrap_result.hec_token:
        state["splunk_hec_token"] = bootstrap_result.hec_token
    save_json(config.state_file, state)

    next_commands = [
        f"autoops investigate --alert autoops_{architecture.app_name.replace(' ', '_').lower()}_checkout_error_rate",
        "autoops watch --port 9000",
        "autoops splunk open",
        "autoops telemetry test",
        f"SPL: index=main sourcetype=autoops | stats count by service, path",
    ]

    return SetupResult(
        architecture=architecture,
        instrumentation_files=instrumentation_files,
        splunk=splunk_result,
        splunk_bootstrap=bootstrap_result,
        collector=collector_result,
        synthetic_test_ok=synthetic_ok,
        repo_root=scan.root,
        next_commands=next_commands,
    )


async def run_setup_pipeline(
    repo: str,
    config: AutoOpsConfig | None = None,
    no_instrument: bool = False,
    setup_splunk: bool = True,
) -> SetupResult:
    """Backward-compatible alias for configure pipeline."""
    return await run_configure_pipeline(
        repo, config, no_instrument=no_instrument, setup_splunk=setup_splunk
    )


async def run_investigation_pipeline(
    alert_name: str,
    affected_services: list[str] | None = None,
    window: str = "30m",
    config: AutoOpsConfig | None = None,
) -> InvestigationResult:
    """Investigation pipeline: evidence (MCP) + RCA (1 Claude) + remediation (1 Claude)."""
    config = config or AutoOpsConfig.from_env()
    start = time.perf_counter()

    from autoops.utils.file_utils import load_json

    arch_data = load_json(config.architecture_file)
    if arch_data:
        architecture = ArchitectureMap.model_validate(arch_data)
    else:
        architecture = ArchitectureMap(
            app_name="unknown",
            services=[],
            databases=[],
            critical_paths=[],
            tech_stack=TechStack(
                languages=["python"],
                frameworks=["fastapi"],
                has_docker=True,
                has_kubernetes=False,
            ),
        )

    services = affected_services or [s.name for s in architecture.services] or ["main"]

    evidence = await collect_evidence(alert_name, services, window, config)
    root_causes = await run_rca(evidence, architecture, config)
    duration = time.perf_counter() - start
    incident = await run_remediation(
        alert_name, root_causes, evidence, architecture, duration, config
    )

    incident_path = config.data_dir / "incidents" / f"{incident.id}.json"
    save_json(incident_path, incident.model_dump())

    return InvestigationResult(incident=incident, duration_seconds=duration)
