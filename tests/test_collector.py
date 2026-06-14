"""Tests for OTel collector config."""

from autoops.telemetry.collector import build_collector_config, write_collector_config


def test_build_collector_config():
    cfg = build_collector_config("test-token-123")
    assert "splunk_hec" in cfg
    assert "test-token-123" in cfg
    assert "4317" in cfg


def test_write_collector_config(tmp_path):
    path = write_collector_config(tmp_path, "tok")
    assert path.exists()
    assert "tok" in path.read_text()
