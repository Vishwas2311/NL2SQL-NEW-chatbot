"""One conventional install file keeps the complete approved package set pinned."""

import tomllib
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]


def test_single_requirements_file_covers_declared_packages_and_platforms():
    assert {path.name for path in ROOT.glob("requirements*") if path.is_file()} == {
        "requirements.txt"
    }
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    packages = [Requirement(line) for line in lines if line and not line.startswith(("#", "--"))]
    by_name = {requirement.name.lower().replace("_", "-"): requirement for requirement in packages}
    assert len(by_name) == len(packages), "Duplicate pins can drift independently"
    for requirement in packages:
        assert requirement.url is None
        assert len(requirement.specifier) == 1
        assert next(iter(requirement.specifier)).operator == "=="
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = project["dependencies"] + [
        dependency for group in project["optional-dependencies"].values() for dependency in group
    ]
    for dependency in declared:
        requirement = Requirement(dependency)
        pinned = by_name[requirement.name.lower().replace("_", "-")]
        assert next(iter(pinned.specifier)).version in requirement.specifier
    windows = {**default_environment(), "sys_platform": "win32", "platform_machine": "AMD64"}
    linux = {**windows, "sys_platform": "linux", "platform_machine": "x86_64"}
    mac = {**windows, "sys_platform": "darwin", "platform_machine": "arm64"}
    for name in ("torch", "sentence-transformers", "transformers", "safetensors"):
        marker = by_name[name].marker
        assert marker is not None and marker.evaluate(windows)
        assert not marker.evaluate(linux) and not marker.evaluate(mac)
    assert by_name["torch"].specifier.contains("2.14.1+cpu")
    for name in ("fastapi", "surrealdb", "oracledb", "redis", "pytest", "pyright", "ruff"):
        assert by_name[name].marker is None
