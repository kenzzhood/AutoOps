"""Tests for cross-platform Docker helpers."""

from unittest.mock import patch

from autoops.utils.docker import check_port, ensure_docker_running


def test_check_port_unlikely_in_use():
    assert check_port(59999) is False


def test_ensure_docker_running_when_daemon_up():
    with patch("autoops.utils.docker.docker_daemon_running", return_value=True):
        ok, msg = ensure_docker_running()
    assert ok is True


def test_ensure_docker_running_missing_binary():
    with patch("autoops.utils.docker.docker_binary", return_value=None):
        with patch("autoops.utils.docker.open_docker_download_page"):
            ok, msg = ensure_docker_running()
    assert ok is False
    assert "Docker" in msg
