"""Splunk integration clients and builders."""

from autoops.splunk.alert_builder import build_alert_stanza
from autoops.splunk.bootstrap import SplunkBootstrapResult, ensure_splunk
from autoops.splunk.dashboard_builder import build_service_dashboard, build_overview_dashboard
from autoops.splunk.mcp_client import SplunkMCPClient
from autoops.splunk.rest_client import SplunkRESTClient

__all__ = [
    "SplunkBootstrapResult",
    "SplunkMCPClient",
    "SplunkRESTClient",
    "build_alert_stanza",
    "build_overview_dashboard",
    "build_service_dashboard",
    "ensure_splunk",
]
