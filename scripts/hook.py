"""Resolve the project's pinned environment for portable local pre-commit hooks."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run the selected quality module using the same interpreter as application tests."""
    executable = Path(".venv") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(executable.resolve()), "-m", *sys.argv[1:]], check=True)


if __name__ == "__main__":
    main()
