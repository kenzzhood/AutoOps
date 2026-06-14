"""Instrumentation Generation Agent — Jinja2 templates, no LLM."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from autoops.models.architecture import ArchitectureMap
from autoops.models.config import AutoOpsConfig
from autoops.utils.file_utils import write_file
from autoops.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def generate_instrumentation(
    architecture: ArchitectureMap,
    repo_root: Path,
    config: AutoOpsConfig | None = None,
    no_write: bool = False,
) -> list[str]:
    """Generate middleware and DB tracing files."""
    config = config or AutoOpsConfig.from_env()
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(),
    )

    written: list[str] = []
    service_name = architecture.services[0].name if architecture.services else architecture.app_name

    middleware_tpl = env.get_template("fastapi_middleware.py.j2")
    middleware_code = middleware_tpl.render(
        service_name=service_name,
        splunk_hec_url=f"{config.splunk_url.rstrip('/')}:8088/services/collector/event".replace(":8000", ":8088"),
        splunk_hec_token=config.splunk_token or "00000000-0000-0000-0000-000000000000",
    )
    middleware_path = repo_root / "autoops_middleware.py"
    if not no_write:
        write_file(middleware_path, middleware_code)
    written.append(str(middleware_path))

    if architecture.databases:
        db_tpl = env.get_template("sqlalchemy_tracing.py.j2")
        db_code = db_tpl.render(database_name=architecture.databases[0].name)
        db_path = repo_root / "autoops_db_tracing.py"
        if not no_write:
            write_file(db_path, db_code)
        written.append(str(db_path))

    logger.info("Generated %d instrumentation files", len(written))
    return written
