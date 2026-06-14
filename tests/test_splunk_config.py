"""Tests for Splunk config agent."""

from unittest.mock import MagicMock, patch

from autoops.agents.splunk_config import configure_splunk


def test_configure_splunk_mock(sample_architecture, config):
    with patch("autoops.agents.splunk_config.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.return_value = True
        client.create_dashboard.return_value = True
        client.create_saved_search.return_value = True
        client.create_alert.return_value = True
        mock_cls.return_value = client

        result = configure_splunk(sample_architecture, config)
        assert len(result.dashboards_created) >= 1
        assert client.create_alert.called


def test_configure_splunk_offline(sample_architecture, config):
    with patch("autoops.agents.splunk_config.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.return_value = False
        mock_cls.return_value = client

        result = configure_splunk(sample_architecture, config)
        assert result.dashboards_created == []
