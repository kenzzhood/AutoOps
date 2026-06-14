"""Splunk REST API client for creating dashboards, alerts, and saved searches."""

from __future__ import annotations

import urllib.parse
from typing import Any

import requests

from autoops.models.config import AutoOpsConfig
from autoops.utils.logger import get_logger

logger = get_logger(__name__)


class SplunkRESTClient:
    """Write-layer Splunk REST client with idempotent create operations."""

    def __init__(self, config: AutoOpsConfig | None = None):
        self.config = config or AutoOpsConfig.from_env()
        self.base = self.config.splunk_rest_base.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (self.config.splunk_username, self.config.splunk_password)
        self.session.verify = False
        self.session.headers.update({"Accept": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def test_connection(self) -> bool:
        try:
            resp = self.session.get(self._url("/services/server/info"), timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Splunk connection failed: %s", exc)
            return False

    def run_search(self, query: str, earliest: str = "-5m", latest: str = "now") -> list[dict[str, Any]]:
        """Run oneshot search via REST (for connection tests)."""
        params = {
            "search": query,
            "earliest_time": earliest,
            "latest_time": latest,
            "output_mode": "json",
        }
        resp = self.session.post(
            self._url("/services/search/jobs/oneshot"),
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def saved_search_exists(self, name: str) -> bool:
        encoded = urllib.parse.quote(name, safe="")
        resp = self.session.get(
            self._url(f"/services/saved/searches/{encoded}"),
            timeout=10,
        )
        return resp.status_code == 200

    def create_saved_search(
        self,
        name: str,
        search: str,
        description: str = "",
        cron_schedule: str = "*/5 * * * *",
    ) -> bool:
        if self.saved_search_exists(name):
            logger.info("Saved search already exists: %s", name)
            return False
        data = {
            "name": name,
            "search": search,
            "description": description,
            "is_scheduled": "1",
            "cron_schedule": cron_schedule,
            "dispatch.earliest_time": "-5m",
            "dispatch.latest_time": "now",
        }
        resp = self.session.post(
            self._url("/services/saved/searches"),
            data=data,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info("Created saved search: %s", name)
            return True
        logger.warning("Failed to create saved search %s: %s", name, resp.text[:200])
        return False

    def dashboard_exists(self, name: str) -> bool:
        encoded = urllib.parse.quote(name, safe="")
        resp = self.session.get(
            self._url(f"/services/data/ui/views/{encoded}"),
            timeout=10,
        )
        return resp.status_code == 200

    def create_dashboard(self, name: str, xml: str) -> bool:
        if self.dashboard_exists(name):
            logger.info("Dashboard already exists: %s", name)
            return False
        data = {"name": name, "eai:data": xml}
        resp = self.session.post(
            self._url("/services/data/ui/views"),
            data=data,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info("Created dashboard: %s", name)
            return True
        logger.warning("Failed to create dashboard %s: %s", name, resp.text[:200])
        return False

    def alert_exists(self, name: str) -> bool:
        return self.saved_search_exists(name)

    def create_alert(
        self,
        name: str,
        search: str,
        description: str,
        alert_type: str = "number of events",
        alert_comparator: str = "greater than",
        alert_threshold: str = "0",
        cron_schedule: str = "*/5 * * * *",
    ) -> bool:
        if self.alert_exists(name):
            logger.info("Alert already exists: %s", name)
            return False
        data = {
            "name": name,
            "search": search,
            "description": description,
            "is_scheduled": "1",
            "cron_schedule": cron_schedule,
            "dispatch.earliest_time": "-5m",
            "dispatch.latest_time": "now",
            "alert_type": alert_type,
            "alert_comparator": alert_comparator,
            "alert_threshold": alert_threshold,
            "alert.suppress": "0",
            "actions": "logevent",
        }
        resp = self.session.post(
            self._url("/services/saved/searches"),
            data=data,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info("Created alert: %s", name)
            return True
        logger.warning("Failed to create alert %s: %s", name, resp.text[:200])
        return False
