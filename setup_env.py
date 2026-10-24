"""Run `python setup_env.py` to create .venv, install requirements.txt and prepare .env."""

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


def main(office: bool = False) -> None:
    """Prepare this project without replacing an existing environment settings file."""
    if sys.version_info[:2] != (3, 13):
        raise SystemExit("Use Python 3.13; office builds must also pass SQLite/FTS5 checks.")
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    diagnostic = str(root / "backend/nl2sql/bootstrap/sqlite_runtime.py")
    if office:
        print("Checking selected office runtime before changing the environment", flush=True)
        subprocess.run(
            [str(python) if python.is_file() else sys.executable, "-I", diagnostic], check=True
        )
    print("1/3 Preparing .venv", flush=True)
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
        if office:
            subprocess.run([str(python), "-I", diagnostic], check=True)
    print("2/3 Installing requirements.txt and the project", flush=True)
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--only-binary=:all:",
            "-r",
            str(root / "requirements.txt"),
        ],
        check=True,
    )
    subprocess.run([str(python), "-m", "pip", "install", "--no-deps", "-e", str(root)], check=True)
    print("3/3 Preparing .env", flush=True)
    template = (root / ".env.example").read_text(encoding="utf-8")
    try:
        with (root / ".env").open("x", encoding="utf-8") as settings:
            settings.write(template)
    except FileExistsError:
        print("Kept your existing .env settings.")
    print("Setup complete. See README.md to initialize and start the synthetic demo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--office", action="store_true", help="Require the patched office runtime before setup"
    )
    main(parser.parse_args().office)
