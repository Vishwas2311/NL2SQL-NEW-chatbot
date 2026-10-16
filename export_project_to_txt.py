"""Run `python export_project_to_txt.py` to create full_project_export.txt beside this file.

Combines readable project files with their relative paths. Excludes local credentials,
databases, environment files, dependency folders, caches, binaries and previous exports.
Uses only Python's standard library; the project files are never modified.
"""

import json
import os
import tempfile
from pathlib import Path

OUTPUT_NAME = "full_project_export.txt"
HEADER = "NL2SQL PROJECT TEXT EXPORT\n"
EXCLUDED_DIRECTORIES = {
    ".git",
    ".local",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".pyright",
    "node_modules",
    "htmlcov",
    "build",
    "dist",
    "secrets",
    "credentials",
    "snapshots",
    "approvals",
    "restricted",
}
TEXT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".sql",
    ".html",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".ps1",
    ".bat",
    ".cmd",
    ".lock",
    ".csv",
    ".tsv",
    ".xml",
    ".typed",
}
TEXT_FILENAMES = {
    ".gitignore",
    ".gitattributes",
    ".python-version",
    ".dockerignore",
    ".editorconfig",
    "dockerfile",
    "makefile",
    "license",
}


def project_files(root: Path, output: Path) -> list[Path]:
    """Prune excluded folders before traversal and never follow filesystem links."""
    files: list[Path] = []

    def traversal_error(error: OSError) -> None:
        raise error

    for directory, folders, filenames in os.walk(root, followlinks=False, onerror=traversal_error):
        parent = Path(directory)
        if (parent / ".metadata-private").exists():
            folders[:] = []
            continue
        folders[:] = sorted(
            folder
            for folder in folders
            if folder.casefold() not in EXCLUDED_DIRECTORIES
            and not folder.casefold().endswith(".egg-info")
            and not (parent / folder).is_symlink()
            and not (parent / folder).is_junction()
        )
        for filename in sorted(filenames):
            path = parent / filename
            name = filename.casefold()
            if (
                path == output
                or path.is_symlink()
                or name.startswith(".env")
                or name.startswith("full_project_export")
                or any(word in name for word in ("credentials", "secrets"))
                or name in {"settings.json", "tokens.json"}
                or name == "source-profile.json"
            ):
                continue
            if path.suffix.casefold() in TEXT_EXTENSIONS or name in TEXT_FILENAMES:
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix().casefold())


def export_project(root: Path) -> tuple[Path, int, tuple[str, ...]]:
    """Atomically regenerate this tool's export; preserve unrelated existing text files."""
    root = root.resolve(strict=True)
    output = root / OUTPUT_NAME
    if output.is_symlink():
        raise ValueError("The export destination must not be a symbolic link")
    if output.exists():
        with output.open("r", encoding="utf-8") as previous:
            if previous.readline() != HEADER:
                raise FileExistsError(f"Refusing to replace an unrelated file: {output}")
    paths = project_files(root, output)
    skipped: list[str] = []
    count = 0
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".project-export-",
            suffix=".tmp",
            dir=root,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(HEADER)
            stream.write("Source, tests, configuration, documentation and UI references.\n")
            stream.write("Local data/secrets, dependencies, caches and binaries are excluded.\n")
            for path in paths:
                relative = path.relative_to(root).as_posix()
                try:
                    content = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    skipped.append(relative)
                    continue
                if "\x00" in content:
                    skipped.append(relative)
                    continue
                if private_json(content):
                    continue
                stream.write(f"\n{'=' * 80}\nFILE: {relative}\n{'=' * 80}\n")
                stream.write(content)
                if not content.endswith("\n"):
                    stream.write("\n")
                count += 1
            stream.write(f"\nEND OF EXPORT — {count} files included.\n")
            if skipped:
                stream.write("Skipped binary/non-UTF-8 files:\n" + "\n".join(skipped) + "\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output, count, tuple(skipped)


def private_json(content: str) -> bool:
    """Recognize copied metadata payloads even outside a marked private directory."""
    try:
        value: object = json.loads(content)
    except ValueError:
        return False
    if isinstance(value, dict):
        if (
            value.get("classification") == "restricted"
            or {"source_kind", "objects"} <= value.keys()
            or "approvals" in value
            or {"source", "source_id"} <= value.keys()
        ):
            return True
        return any(
            private_json(json.dumps(child))
            for child in value.values()
            if isinstance(child, (dict, list))
        )
    if isinstance(value, list):
        return any(
            private_json(json.dumps(child)) for child in value if isinstance(child, (dict, list))
        )
    return False


def main() -> None:
    """Anchor the export to this script, regardless of the terminal's working directory."""
    output, count, skipped = export_project(Path(__file__).resolve().parent)
    print(
        f"Created {output}\nIncluded {count} project files; "
        f"skipped {len(skipped)} binary/text-format files."
    )


if __name__ == "__main__":
    main()
