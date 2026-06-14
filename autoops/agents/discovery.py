"""Architecture Discovery Agent — Claude tool_use."""

from __future__ import annotations

import json
from typing import Any

from autoops.llm.router import call_with_tool
from autoops.models.architecture import (
    APIEndpoint,
    ArchitectureMap,
    CriticalPath,
    Database,
    Service,
    TechStack,
)
from autoops.models.config import AutoOpsConfig
from autoops.scanner.code_analyzer import analyze_repo_python, extract_sqlalchemy_models
from autoops.scanner.infra_analyzer import analyze_infrastructure
from autoops.scanner.repo_scanner import RepoScanResult, scan_repository
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

DISCOVERY_TOOL = {
    "name": "report_architecture",
    "description": "Report the discovered architecture of the application",
    "input_schema": {
        "type": "object",
        "properties": {
            "app_name": {"type": "string"},
            "services": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "file_path": {"type": "string"},
                        "endpoints": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "method": {"type": "string"},
                                    "handler_function": {"type": "string"},
                                    "is_critical": {"type": "boolean"},
                                },
                                "required": ["path", "method", "handler_function"],
                            },
                        },
                        "dependencies": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "type", "file_path"],
                },
            },
            "databases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "tables_or_collections": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "connection_var": {"type": "string"},
                    },
                    "required": ["name", "type", "connection_var"],
                },
            },
            "external_apis": {"type": "array", "items": {"type": "string"}},
            "critical_paths": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "services": {"type": "array", "items": {"type": "string"}},
                        "endpoints": {"type": "array", "items": {"type": "string"}},
                        "slo_latency_ms": {"type": "integer"},
                        "error_budget_pct": {"type": "number"},
                    },
                    "required": ["name", "services", "endpoints"],
                },
            },
            "tech_stack": {
                "type": "object",
                "properties": {
                    "languages": {"type": "array", "items": {"type": "string"}},
                    "frameworks": {"type": "array", "items": {"type": "string"}},
                    "has_docker": {"type": "boolean"},
                    "has_kubernetes": {"type": "boolean"},
                },
                "required": ["languages", "frameworks", "has_docker", "has_kubernetes"],
            },
            "log_paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["app_name", "services", "databases", "critical_paths", "tech_stack"],
    },
}


def _heuristic_architecture(scan: RepoScanResult) -> ArchitectureMap:
    """Fallback when Claude API unavailable."""
    infra = analyze_infrastructure(scan.root)
    py_services = analyze_repo_python(scan.root)
    app_name = scan.root.name

    services: list[Service] = []
    for ps in py_services:
        endpoints = [
            APIEndpoint(
                path=e.path,
                method=e.method,
                handler_function=e.handler_function,
                is_critical="/checkout" in e.path,
            )
            for e in ps.endpoints
        ]
        services.append(
            Service(
                name=ps.name,
                type="fastapi" if any("fastapi" in i.lower() for i in ps.imports) else "service",
                file_path=ps.file_path,
                endpoints=endpoints,
            )
        )

    if not services:
        services.append(
            Service(name="main", type="fastapi", file_path="main.py")
        )

    tables: list[str] = []
    for path in scan.root.rglob("models.py"):
        for m in extract_sqlalchemy_models(path):
            tables.append(m.table_name or m.name)

    databases = [
        Database(
            name=db.get("type", "postgresql"),
            type=db.get("type", "postgresql"),
            connection_var="DATABASE_URL",
            tables_or_collections=tables,
        )
        for db in infra.databases
    ] or [
        Database(
            name="primary_db",
            type="postgresql",
            connection_var="DATABASE_URL",
            tables_or_collections=tables,
        )
    ]

    return ArchitectureMap(
        app_name=app_name,
        services=services,
        databases=databases,
        critical_paths=[
            CriticalPath(
                name="user_checkout",
                services=[services[0].name],
                endpoints=["POST /checkout"],
                slo_latency_ms=2000,
                error_budget_pct=0.05,
            )
        ],
        tech_stack=TechStack(
            languages=["python"],
            frameworks=["fastapi"] if services else [],
            has_docker=infra.has_docker,
            has_kubernetes=infra.has_kubernetes,
        ),
    )


async def run_discovery(
    repo: str,
    config: AutoOpsConfig | None = None,
) -> ArchitectureMap:
    """Run discovery agent: scan repo + Azure OpenAI function calling."""
    config = config or AutoOpsConfig.from_env()
    scan = scan_repository(repo)
    logger.info("Scanned %d files from %s", len(scan.file_tree), scan.root)

    from autoops.config.store import ConfigStore

    store = ConfigStore()
    profile = store.get_profile()
    if not profile and not config.llm_configured:
        logger.warning("No LLM provider configured — using heuristic discovery")
        return _heuristic_architecture(scan)
    if profile:
        config = store.profile_to_autoops_config(profile)

    context = scan.to_context_blob()
    try:
        data: dict[str, Any] = call_with_tool(
            config,
            DISCOVERY_TOOL,
            (
                "Analyze this codebase and report its architecture using the "
                "report_architecture tool. Identify services, databases, "
                "critical paths (especially checkout/login), and tech stack.\n\n"
                f"{context}"
            ),
            profile=profile,
            store_secrets=store,
        )
        arch = ArchitectureMap.model_validate(data)
    except Exception as exc:
        logger.warning("LLM discovery failed (%s) — using heuristic discovery", exc)

        return _heuristic_architecture(scan)
    logger.info(
        "Discovered %d services, %d databases, %d critical paths",
        len(arch.services),
        len(arch.databases),
        len(arch.critical_paths),
    )
    return arch
