"""AST analysis of Python files."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedEndpoint:
    path: str
    method: str
    handler_function: str


@dataclass
class ParsedService:
    name: str
    file_path: str
    endpoints: list[ParsedEndpoint] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class ParsedModel:
    name: str
    table_name: str | None
    file_path: str


def _decorator_route(dec: ast.AST) -> tuple[str | None, str | None]:
    """Extract method and path from @app.get('/path') style decorators."""
    if not isinstance(dec, ast.Call):
        return None, None
    func = dec.func
    if isinstance(func, ast.Attribute):
        method = func.attr.upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            return None, None
        if dec.args and isinstance(dec.args[0], ast.Constant):
            return method, str(dec.args[0].value)
    return None, None


def analyze_python_file(path: Path) -> ParsedService | None:
    """Parse FastAPI-style routes from a Python file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return None

    service = ParsedService(name=path.stem, file_path=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                service.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            service.imports.append(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                method, route_path = _decorator_route(dec)
                if method and route_path:
                    service.endpoints.append(
                        ParsedEndpoint(
                            path=route_path,
                            method=method,
                            handler_function=node.name,
                        )
                    )
    if service.endpoints or "fastapi" in " ".join(service.imports).lower():
        return service
    return None


def analyze_repo_python(root: Path) -> list[ParsedService]:
    """Analyze all Python files in repo."""
    services: list[ParsedService] = []
    for path in root.rglob("*.py"):
        if any(p in path.parts for p in (".git", "venv", ".venv", "__pycache__")):
            continue
        parsed = analyze_python_file(path)
        if parsed:
            services.append(parsed)
    return services


def extract_sqlalchemy_models(path: Path) -> list[ParsedModel]:
    """Extract SQLAlchemy model class names from a file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []

    models: list[ParsedModel] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table_name = None
        for base in node.bases:
            base_name = ""
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name in {"Base", "DeclarativeBase"}:
                for item in node.body:
                    if (
                        isinstance(item, ast.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast.Name)
                        and item.targets[0].id == "__tablename__"
                        and isinstance(item.value, ast.Constant)
                    ):
                        table_name = str(item.value.value)
                models.append(
                    ParsedModel(name=node.name, table_name=table_name, file_path=str(path))
                )
    return models
