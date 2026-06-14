"""AutoOps AI agents."""

from autoops.agents.discovery import run_discovery
from autoops.agents.evidence import collect_evidence
from autoops.agents.instrumentation import generate_instrumentation
from autoops.agents.orchestrator import run_investigation_pipeline, run_setup_pipeline
from autoops.agents.rca import run_rca
from autoops.agents.remediation import run_remediation
from autoops.agents.splunk_config import configure_splunk

__all__ = [
    "collect_evidence",
    "configure_splunk",
    "generate_instrumentation",
    "run_discovery",
    "run_investigation_pipeline",
    "run_rca",
    "run_remediation",
    "run_setup_pipeline",
]
