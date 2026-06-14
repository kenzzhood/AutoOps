"""Tests for Splunk dashboard and alert builders."""

from autoops.splunk.alert_builder import build_checkout_alert, build_error_rate_search
from autoops.splunk.dashboard_builder import build_overview_dashboard, build_service_dashboard


def test_service_dashboard_xml():
    xml = build_service_dashboard("Demo Shop", "main")
    assert "Demo Shop" in xml
    assert "main" in xml
    assert "<dashboard" in xml


def test_overview_dashboard():
    xml = build_overview_dashboard("Demo Shop")
    assert "Service Health Overview" in xml


def test_error_rate_search():
    search = build_error_rate_search("main")
    assert "service=\"main\"" in search
    assert "ERROR" in search


def test_checkout_alert():
    alert = build_checkout_alert("demo_shop")
    assert "checkout" in alert["search"].lower()
