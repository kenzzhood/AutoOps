"""Tests for repository scanner."""

from pathlib import Path

from autoops.scanner.code_analyzer import analyze_python_file
from autoops.scanner.infra_analyzer import analyze_infrastructure
from autoops.scanner.repo_scanner import scan_repository


def test_scan_demo_app():
    repo = Path(__file__).parent.parent / "demo-app"
    result = scan_repository(str(repo))
    assert result.root.exists()
    assert len(result.file_tree) > 0
    assert any("main.py" in f for f in result.key_files)


def test_analyze_main_py():
    main_py = Path(__file__).parent.parent / "demo-app" / "main.py"
    service = analyze_python_file(main_py)
    assert service is not None
    paths = {e.path for e in service.endpoints}
    assert "/checkout" in paths


def test_infra_analyzer():
    repo = Path(__file__).parent.parent / "demo-app"
    infra = analyze_infrastructure(repo)
    assert infra.has_docker is True
