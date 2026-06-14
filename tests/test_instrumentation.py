"""Tests for instrumentation agent."""

from pathlib import Path

from autoops.agents.instrumentation import generate_instrumentation


def test_generate_instrumentation(sample_architecture, tmp_path):
    files = generate_instrumentation(sample_architecture, tmp_path)
    assert len(files) >= 1
    middleware = tmp_path / "autoops_middleware.py"
    assert middleware.exists()
    content = middleware.read_text()
    assert "AutoOpsMiddleware" in content
    assert "autoops" in content
