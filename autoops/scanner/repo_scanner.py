"""File system and git repository scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from autoops.utils.file_utils import (
    clone_or_use_repo,
    list_repo_files,
    read_text_file,
)


PRIORITY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "main.py",
    "app.py",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    ".env.example",
}

ROUTE_HINTS = ("routes", "router", "api", "views", "handlers")
MODEL_HINTS = ("models", "schema", "schemas", "entities")


@dataclass
class RepoScanResult:
    root: Path
    file_tree: list[str]
    key_files: dict[str, str] = field(default_factory=dict)
    is_temp_clone: bool = False

    def to_context_blob(self, max_chars: int = 180_000) -> str:
        """Build token-budgeted context for Claude discovery."""
        parts = ["# File Tree\n"] + self.file_tree[:500]
        parts.append("\n# Key File Contents\n")
        used = sum(len(p) for p in parts)
        for name, content in self.key_files.items():
            chunk = f"\n## {name}\n```\n{content}\n```\n"
            if used + len(chunk) > max_chars:
                break
            parts.append(chunk)
            used += len(chunk)
        return "".join(parts)


def _is_priority(path: Path) -> bool:
    name = path.name.lower()
    if name in PRIORITY_FILES:
        return True
    lower = str(path).lower()
    return any(h in lower for h in ROUTE_HINTS + MODEL_HINTS)


def scan_repository(repo: str) -> RepoScanResult:
    """Scan repo from URL or local path."""
    root = clone_or_use_repo(repo)
    is_temp = str(root).startswith("/tmp") or "autoops-repo-" in str(root)
    all_files = list_repo_files(root)
    file_tree = [
        str(f.relative_to(root)).replace("\\", "/") for f in all_files
    ]

    key_files: dict[str, str] = {}
    for f in all_files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        if _is_priority(f) or f.suffix in {".py", ".yml", ".yaml", ".toml"}:
            if f.stat().st_size > 500_000:
                continue
            key_files[rel] = read_text_file(f, max_lines=200)

    return RepoScanResult(
        root=root,
        file_tree=file_tree,
        key_files=key_files,
        is_temp_clone=is_temp,
    )
