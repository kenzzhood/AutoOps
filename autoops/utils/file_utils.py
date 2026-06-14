"""File and JSON persistence utilities."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def expand_path(path: str | Path) -> Path:
    """Expand ~ and env vars in a path."""
    return Path(os.path.expandvars(os.path.expanduser(str(path))))


def ensure_data_dir() -> Path:
    """Ensure ~/.autoops (or AUTOOPS_DATA_DIR) exists."""
    data_dir = expand_path(os.getenv("AUTOOPS_DATA_DIR", "~/.autoops"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def save_json(path: Path, data: Any) -> None:
    """Write JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    tmp.replace(path)


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file or return default."""
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def clone_or_use_repo(repo: str) -> Path:
    """Clone git URL to temp dir or return local path."""
    repo = repo.strip()
    if repo.startswith("http://") or repo.startswith("https://") or repo.startswith("git@"):
        tmp = Path(tempfile.mkdtemp(prefix="autoops-repo-"))
        subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(tmp)],
            check=True,
            capture_output=True,
        )
        return tmp
    path = expand_path(repo)
    if not path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo}")
    return path.resolve()


def read_text_file(path: Path, max_lines: int | None = None) -> str:
    """Read file with optional line limit."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if max_lines is None:
        return text
    lines = text.splitlines()[:max_lines]
    return "\n".join(lines)


def list_repo_files(root: Path, ignore_dirs: set[str] | None = None) -> list[Path]:
    """List all files under root, excluding common ignore dirs."""
    ignore = ignore_dirs or {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".autoops",
        "dist",
        "build",
        ".pytest_cache",
    }
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for name in filenames:
            files.append(Path(dirpath) / name)
    return sorted(files)


def write_file(path: Path, content: str) -> None:
    """Write text file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_tree(src: Path, dst: Path) -> None:
    """Copy directory tree."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
