"""Tests for expanded Splunk defaults."""

from autoops.splunk.alert_builder import (
    build_5xx_spike_search,
    build_db_latency_search,
    build_no_data_search,
    build_p95_latency_search,
)
from autoops.splunk.dashboard_builder import (
    build_deployment_dashboard,
    build_incident_dashboard,
)


def test_new_dashboards():
    assert "Deployment" in build_deployment_dashboard("App")
    assert "Incident" in build_incident_dashboard("App")


def test_new_searches():
    assert "p95" in build_p95_latency_search()
    assert "db_query" in build_db_latency_search()
    assert "events < 1" in build_no_data_search()
    assert "status>=500" in build_5xx_spike_search()
