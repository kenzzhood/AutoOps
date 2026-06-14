from pydantic import BaseModel
from typing import List, Optional, Literal, Any
from datetime import datetime


class RootCause(BaseModel):
    hypothesis: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str]
    component: str


class ImpactAssessment(BaseModel):
    users_affected_estimate: int
    revenue_impact: str  # "high", "medium", "low", "unknown"
    services_degraded: List[str]


class RemediationStep(BaseModel):
    action: str
    command: Optional[str] = None  # actual shell command if applicable
    risk: str  # "low", "medium", "high"
    estimated_time_minutes: int


class Incident(BaseModel):
    id: str
    alert_name: str
    severity: Literal["critical", "high", "medium", "low"]
    started_at: datetime
    affected_services: List[str]
    error_rate: Optional[float] = None
    root_causes: List[RootCause]
    impact: ImpactAssessment
    remediation_steps: List[RemediationStep]
    executive_summary: str  # 2-3 sentences for non-technical audience
    technical_summary: str  # full technical details
    investigation_duration_seconds: float


class EvidencePackage(BaseModel):
    """Collected evidence from Splunk MCP queries."""

    alert_name: str
    affected_services: List[str]
    window: str
    error_logs: List[dict[str, Any]] = []
    latency_metrics: List[dict[str, Any]] = []
    deployment_events: List[dict[str, Any]] = []
    database_metrics: List[dict[str, Any]] = []
    container_health: List[dict[str, Any]] = []
    raw_queries: List[str] = []
