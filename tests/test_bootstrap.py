"""Tests for Splunk Docker bootstrap."""

from unittest.mock import MagicMock, patch

import pytest

from autoops.models.config import AutoOpsConfig
from autoops.splunk.bootstrap import ensure_splunk


@pytest.fixture
def config(tmp_path):
    return AutoOpsConfig(
        azure_openai_api_key="",
        azure_openai_endpoint="",
        azure_openai_deployment="",
        splunk_url="http://localhost:8000",
        splunk_username="admin",
        splunk_password="changeme",
        splunk_token="",
        splunk_mcp_url="http://localhost:8089",
        data_dir=tmp_path,
    )


def test_ensure_splunk_already_running(config):
    with patch("autoops.splunk.bootstrap.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.return_value = True
        mock_cls.return_value = client

        result = ensure_splunk(config)

    assert result.success is True
    assert result.already_running is True
    assert result.container_started is False


def test_ensure_splunk_starts_existing_container(config):
    with patch("autoops.splunk.bootstrap.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.side_effect = [False, True]
        mock_cls.return_value = client

        with patch("autoops.splunk.bootstrap.ensure_docker_running", return_value=(True, "")):
            with patch("autoops.splunk.bootstrap.container_exists", return_value=True):
                with patch("autoops.splunk.bootstrap.container_running", return_value=False):
                    with patch("autoops.splunk.bootstrap.run_docker") as mock_run:
                        with patch("autoops.splunk.bootstrap._wait_for_splunk", return_value=True):
                            with patch(
                                "autoops.splunk.bootstrap._verify_or_create_hec",
                                return_value="tok-123",
                            ):
                                result = ensure_splunk(config)

    assert result.success is True
    assert result.container_started is True
    assert config.splunk_token == "tok-123"
    mock_run.assert_called()


def test_ensure_splunk_creates_new_container(config):
    with patch("autoops.splunk.bootstrap.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.side_effect = [False, True]
        mock_cls.return_value = client

        with patch("autoops.splunk.bootstrap.ensure_docker_running", return_value=(True, "")):
            with patch("autoops.splunk.bootstrap.container_exists", return_value=False):
                with patch("autoops.splunk.bootstrap.container_running", return_value=False):
                    with patch("autoops.splunk.bootstrap.run_docker"):
                        with patch("autoops.splunk.bootstrap._wait_for_splunk", return_value=True):
                            with patch(
                                "autoops.splunk.bootstrap._verify_or_create_hec",
                                return_value="new-tok",
                            ):
                                result = ensure_splunk(config)

    assert result.success is True
    assert result.container_started is True
    assert config.splunk_token == "new-tok"


def test_ensure_splunk_docker_missing(config):
    with patch("autoops.splunk.bootstrap.SplunkRESTClient") as mock_cls:
        client = MagicMock()
        client.test_connection.return_value = False
        mock_cls.return_value = client

        with patch(
            "autoops.splunk.bootstrap.ensure_docker_running",
            return_value=(False, "install Docker"),
        ):
            with patch("autoops.splunk.bootstrap.webbrowser.open"):
                result = ensure_splunk(config)

    assert result.success is False
    assert "Docker" in result.message


def test_config_from_env_loads_token_from_state(tmp_path, monkeypatch):
    (tmp_path / "state.json").write_text('{"splunk_hec_token": "persisted-token"}')
    monkeypatch.setenv("AUTOOPS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SPLUNK_TOKEN", raising=False)

    cfg = AutoOpsConfig.from_env()
    assert cfg.splunk_token == "persisted-token"
