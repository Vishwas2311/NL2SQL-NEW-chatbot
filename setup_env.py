"""Run `python setup_env.py` to create .venv, install core dependencies and prepare .env."""

import os
import subprocess
import sys
import venv
from pathlib import Path


def main() -> None:
    """Prepare this project without replacing an existing environment settings file."""
    if sys.version_info[:2] != (3, 13):
        raise SystemExit("Use Python 3.13; the verified project baseline is Python 3.13.16.")
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    print("1/3 Preparing .venv", flush=True)
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    print("2/3 Installing pinned core dependencies and the project", flush=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(root / "requirements-core.lock")],
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
    main()
