"""Keep the reorganized package's dependency direction enforceable."""

import ast
from pathlib import Path

import pytest


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
            modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [item.name for item in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for module in modules:
                parts = module.split(".")
                if len(parts) > 1 and parts[0] == "nl2sql" and parts[1] in forbidden:
                    violations.append(f"{path}:{node.lineno}: {module}")
                if layer == "domain" and parts[0] in {"sqlite3", "httpx", "redis", "fastapi"}:
                    violations.append(f"{path}:{node.lineno}: domain imports I/O adapter")
    assert not violations, "\n".join(violations)
