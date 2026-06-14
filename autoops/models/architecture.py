from pydantic import BaseModel
from typing import List, Optional


class APIEndpoint(BaseModel):
    path: str
    method: str
    handler_function: str
    is_critical: bool = False


class Service(BaseModel):
    name: str
    type: str  # "fastapi", "worker", "scheduler", etc
    file_path: str
    endpoints: List[APIEndpoint] = []
    dependencies: List[str] = []  # other service names


class Database(BaseModel):
    name: str
    type: str  # "postgresql", "redis", "mongodb"
    tables_or_collections: List[str] = []
    connection_var: str  # env var name for connection string


class CriticalPath(BaseModel):
    name: str  # "user_checkout", "user_login", "payment_processing"
    services: List[str]
    endpoints: List[str]
    slo_latency_ms: int = 2000
    error_budget_pct: float = 0.05


class TechStack(BaseModel):
    languages: List[str]
    frameworks: List[str]
    has_docker: bool
    has_kubernetes: bool


class ArchitectureMap(BaseModel):
    app_name: str
    services: List[Service]
    databases: List[Database]
    external_apis: List[str] = []
    critical_paths: List[CriticalPath]
    tech_stack: TechStack
    log_paths: List[str] = []
