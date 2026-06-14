"""CLI help snapshot tests."""

from typer.testing import CliRunner

from autoops.cli import app

runner = CliRunner()


def test_root_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "configure" in result.stdout
    assert "setup" in result.stdout


def test_provider_help():
    result = runner.invoke(app, ["provider", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout


def test_splunk_help():
    result = runner.invoke(app, ["splunk", "--help"])
    assert result.exit_code == 0
    assert "start" in result.stdout
