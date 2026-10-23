"""Keep the reorganized package's dependency direction enforceable."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest


def imported_modules(node, path, root):
    if isinstance(node, ast.Import):
        return [item.name for item in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    module = node.module or ""
    if node.level:
        package = ".".join(("nl2sql", *path.relative_to(root).parent.parts))
        module = resolve_name("." * node.level + module, package)
    return [module, *(module + "." + alias.name for alias in node.names)]


def test_relative_import_resolves_to_the_actual_layer(tmp_path):
    path = tmp_path / "application" / "example.py"
    nodes = ast.parse("from ..infrastructure import sessions\nfrom .. import infrastructure").body
    for node in nodes:
        assert any(
            item.startswith("nl2sql.infrastructure")
            for item in imported_modules(node, path, tmp_path)
        )


@pytest.mark.parametrize(
    "layer,forbidden",
    [
        ("domain", {"application", "infrastructure", "bootstrap", "api", "cli", "evaluation"}),
        ("application", {"infrastructure", "bootstrap", "api", "cli", "evaluation"}),
        ("infrastructure", {"bootstrap", "api", "cli", "evaluation"}),
        ("api", {"infrastructure", "bootstrap", "cli", "evaluation"}),
    ],
)
def test_dependency_direction(layer, forbidden):
    root = Path("backend/nl2sql")
    violations = []
    for path in (root / layer).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = imported_modules(node, path, root)
            for module in modules:
                parts = module.split(".")
                if len(parts) > 1 and parts[0] == "nl2sql" and parts[1] in forbidden:
                    violations.append(f"{path}:{node.lineno}: {module}")
                if layer == "domain" and parts[0] in {
                    "sqlite3",
                    "httpx",
                    "redis",
                    "fastapi",
                    "ladybug",
                    "oracledb",
                    "requests",
                    "subprocess",
                }:
                    violations.append(f"{path}:{node.lineno}: domain imports I/O adapter")
    assert not violations, "\n".join(violations)
