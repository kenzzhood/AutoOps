"""Docker, docker-compose, and Kubernetes parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InfraAnalysis:
    has_docker: bool = False
    has_kubernetes: bool = False
    databases: list[dict[str, str]] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)


DB_IMAGE_PATTERNS = {
    "postgresql": re.compile(r"postgres", re.I),
    "redis": re.compile(r"redis", re.I),
    "mongodb": re.compile(r"mongo", re.I),
    "mysql": re.compile(r"mysql|mariadb", re.I),
}


def _parse_compose(content: str) -> InfraAnalysis:
    result = InfraAnalysis(has_docker=True)
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("services:"):
            continue
        svc_match = re.match(r"^(\w[\w-]*):", line)
        if svc_match and not line.startswith("-"):
            name = svc_match.group(1)
            if name not in {"services", "volumes", "networks", "version"}:
                result.services.append(name)
        image_match = re.search(r"image:\s*['\"]?([\w./:-]+)", line, re.I)
        if image_match:
            image = image_match.group(1)
            for db_type, pattern in DB_IMAGE_PATTERNS.items():
                if pattern.search(image):
                    result.databases.append({"type": db_type, "image": image})
        env_match = re.search(r"\$\{(\w+)\}", line)
        if env_match:
            result.env_vars.append(env_match.group(1))
    return result


def analyze_infrastructure(root: Path) -> InfraAnalysis:
    """Scan repo for Docker/K8s infrastructure."""
    result = InfraAnalysis()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        rel = str(path.relative_to(root))
        if name == "dockerfile" or name.startswith("dockerfile."):
            result.has_docker = True
        if name in {"docker-compose.yml", "docker-compose.yaml"}:
            result.has_docker = True
            try:
                compose = _parse_compose(path.read_text(encoding="utf-8", errors="replace"))
                result.services.extend(compose.services)
                result.databases.extend(compose.databases)
                result.env_vars.extend(compose.env_vars)
            except OSError:
                pass
        if "k8s" in rel.lower() or "kubernetes" in rel.lower() or name.endswith((".yaml", ".yml")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "kind: Deployment" in text or "kind: Service" in text:
                    result.has_kubernetes = True
            except OSError:
                pass
    result.services = sorted(set(result.services))
    result.env_vars = sorted(set(result.env_vars))
    return result
