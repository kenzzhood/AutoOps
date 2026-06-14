"""Tests for Pydantic models."""

import json
from pathlib import Path

from autoops.models.architecture import ArchitectureMap
from autoops.models.incident import EvidencePackage, Incident, RootCause


def test_architecture_map_from_fixture():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "sample_architecture.json").read_text()
    )
    arch = ArchitectureMap.model_validate(data)
    assert arch.app_name == "demo-shop"
    assert len(arch.services) == 1
    assert arch.services[0].endpoints[3].path == "/checkout"


def test_evidence_package_defaults():
    ep = EvidencePackage(alert_name="test", affected_services=["main"], window="30m")
    assert ep.error_logs == []
    assert ep.raw_queries == []


def test_root_cause_validation():
    rc = RootCause(
        hypothesis="N+1 query",
        confidence=0.85,
        evidence=["db latency spike"],
        component="checkout",
    )
    assert rc.confidence == 0.85
