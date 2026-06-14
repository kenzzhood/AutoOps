"""Tests for configure pipeline orchestration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from autoops.agents.orchestrator import run_configure_pipeline
from autoops.agents.splunk_config import SplunkConfigResult
from autoops.models.architecture import ArchitectureMap, TechStack
from autoops.models.config import AutoOpsConfig
from autoops.scanner.repo_scanner import RepoScanResult


def _architecture() -> ArchitectureMap:
    return ArchitectureMap(
        app_name="demo",
        services=[],
        databases=[],
        critical_paths=[],
        tech_stack=TechStack(
            languages=["python"],
            frameworks=["fastapi"],
            has_docker=True,
            has_kubernetes=False,
        ),
    )


def test_configure_pipeline_order(tmp_path):
    config = AutoOpsConfig(
        azure_openai_api_key="k",
        azure_openai_endpoint="https://x.openai.azure.com/",
        azure_openai_deployment="gpt-4o",
        splunk_token="hec-tok",
        data_dir=tmp_path,
    )
    calls: list[str] = []
    scan = RepoScanResult(root=tmp_path, file_tree=[])

    def track(name):
        def _inner(*_a, **_k):
            calls.append(name)
            if name == "scan":
                return scan
            if name == "discover":
                return _architecture()
            if name == "instrument":
                return []
            if name == "splunk_config":
                return SplunkConfigResult(
                    dashboards_created=[],
                    alerts_created=[],
                    saved_searches_created=[],
                )
            if name == "splunk":
                return MagicMock(success=True, hec_token="hec-tok")
            if name == "collector":
                return MagicMock(success=True)
            if name == "test_event":
                return True
            return MagicMock()

        return _inner

    with patch("autoops.agents.orchestrator.ConfigStore") as mock_store:
        mock_store.return_value.get_profile.return_value = None
        with patch("autoops.agents.orchestrator.scan_repository", side_effect=track("scan")):
            with patch("autoops.agents.orchestrator.ensure_splunk", side_effect=track("splunk")):
                with patch(
                    "autoops.agents.orchestrator.ensure_collector",
                    side_effect=track("collector"),
                ):
                    with patch(
                        "autoops.agents.orchestrator.run_discovery",
                        new=AsyncMock(side_effect=track("discover")),
                    ):
                        with patch(
                            "autoops.agents.orchestrator.generate_instrumentation",
                            side_effect=track("instrument"),
                        ):
                            with patch(
                                "autoops.agents.orchestrator.configure_splunk",
                                side_effect=track("splunk_config"),
                            ):
                                with patch(
                                    "autoops.agents.orchestrator.send_test_event",
                                    side_effect=track("test_event"),
                                ):
                                    asyncio.run(
                                        run_configure_pipeline(
                                            str(tmp_path),
                                            config=config,
                                            no_instrument=False,
                                        )
                                    )

    assert calls.index("splunk") < calls.index("collector")
    assert calls.index("scan") < calls.index("discover")
    assert calls.index("discover") < calls.index("instrument")
    assert calls.index("splunk_config") < calls.index("test_event")
