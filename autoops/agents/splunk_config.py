"""Splunk Config Agent — REST API writes, no LLM."""

from __future__ import annotations

from dataclasses import dataclass, field

from autoops.models.architecture import ArchitectureMap
from autoops.models.config import AutoOpsConfig
from autoops.splunk.alert_builder import (
    build_5xx_spike_search,
    build_checkout_alert,
    build_db_latency_search,
    build_deployment_search,
    build_error_rate_search,
    build_latency_search,
    build_no_data_search,
    build_p95_latency_search,
)
from autoops.splunk.dashboard_builder import (
    build_database_dashboard,
    build_deployment_dashboard,
    build_incident_dashboard,
    build_overview_dashboard,
    build_service_dashboard,
)
from autoops.splunk.rest_client import SplunkRESTClient
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SplunkConfigResult:
    dashboards_created: list[str] = field(default_factory=list)
    alerts_created: list[str] = field(default_factory=list)
    saved_searches_created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def configure_splunk(
    architecture: ArchitectureMap,
    config: AutoOpsConfig | None = None,
) -> SplunkConfigResult:
    """Create saved searches, alerts, and dashboards idempotently."""
    config = config or AutoOpsConfig.from_env()
    client = SplunkRESTClient(config)
    result = SplunkConfigResult()

    if not client.test_connection():
        logger.warning(
            "Splunk unavailable at %s — skipping config (retry when Splunk is up)",
            config.splunk_rest_base,
        )
        return result

    app = architecture.app_name.replace(" ", "_").lower()

    overview_name = f"autoops_{app}_overview"
    if client.create_dashboard(overview_name, build_overview_dashboard(architecture.app_name)):
        result.dashboards_created.append("Service Health Overview")
    else:
        result.skipped.append(overview_name)

    db_name = f"autoops_{app}_database"
    if client.create_dashboard(db_name, build_database_dashboard(architecture.app_name)):
        result.dashboards_created.append("Database Performance")
    else:
        result.skipped.append(db_name)

    deploy_name = f"autoops_{app}_deployments"
    if client.create_dashboard(deploy_name, build_deployment_dashboard(architecture.app_name)):
        result.dashboards_created.append("Deployment Timeline")
    else:
        result.skipped.append(deploy_name)

    incident_name = f"autoops_{app}_incident"
    if client.create_dashboard(incident_name, build_incident_dashboard(architecture.app_name)):
        result.dashboards_created.append("Incident Investigation")
    else:
        result.skipped.append(incident_name)

    extra_searches = [
        (f"autoops_{app}_p95_latency", build_p95_latency_search(), "P95 latency over SLO"),
        (f"autoops_{app}_db_latency", build_db_latency_search(), "Database latency regression"),
        (f"autoops_{app}_deployments", build_deployment_search(), "Recent deployments"),
        (f"autoops_{app}_no_data", build_no_data_search(), "Ingestion stopped"),
    ]
    for name, search, desc in extra_searches:
        if client.create_saved_search(name, search, desc):
            result.saved_searches_created.append(name)
        else:
            result.skipped.append(name)

    spike_name = f"autoops_{app}_5xx_spike"
    spike_search = build_5xx_spike_search()
    if client.create_alert(spike_name, spike_search, "Sustained 5xx spike"):
        result.alerts_created.append(spike_name)
    else:
        result.skipped.append(spike_name)

    nodata_name = f"autoops_{app}_no_data_alert"
    if client.create_alert(nodata_name, build_no_data_search(), "No telemetry ingested"):
        result.alerts_created.append(nodata_name)
    else:
        result.skipped.append(nodata_name)

    for service in architecture.services:
        svc = service.name.replace(" ", "_").lower()
        dash_name = f"autoops_{app}_{svc}_health"
        if client.create_dashboard(
            dash_name,
            build_service_dashboard(architecture.app_name, service.name),
        ):
            result.dashboards_created.append(f"{service.name} Health")
        else:
            result.skipped.append(dash_name)

        err_search = build_error_rate_search(service.name)
        err_name = f"autoops_{app}_{svc}_error_rate"
        if client.create_saved_search(err_name, err_search, f"Error rate for {service.name}"):
            result.saved_searches_created.append(err_name)
        else:
            result.skipped.append(err_name)

        lat_search = build_latency_search(service.name)
        lat_name = f"autoops_{app}_{svc}_latency"
        if client.create_saved_search(lat_name, lat_search, f"Latency for {service.name}"):
            result.saved_searches_created.append(lat_name)
        else:
            result.skipped.append(lat_name)

        alert_name = f"autoops_{app}_{svc}_error_alert"
        if client.create_alert(alert_name, err_search, f"High error rate: {service.name}"):
            result.alerts_created.append(alert_name)
        else:
            result.skipped.append(alert_name)

    checkout = build_checkout_alert(app)
    if client.create_alert(
        checkout["name"],
        checkout["search"],
        checkout["description"],
    ):
        result.alerts_created.append(checkout["name"])
    else:
        result.skipped.append(checkout["name"])

    logger.info(
        "Splunk config: %d dashboards, %d alerts, %d saved searches",
        len(result.dashboards_created),
        len(result.alerts_created),
        len(result.saved_searches_created),
    )
    return result
