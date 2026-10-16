"""Run the same mandatory backend gates locally and in CI."""

import subprocess
import sys


def main() -> None:
    """Fail fast; a skipped command is never recorded as passing."""
    commands = (
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["pylint", "backend/nl2sql"],
        ["pyright"],
        ["pytest", "-q"],
        ["pre_commit", "run", "--all-files"],
    )
    for command in commands:
        print("Running:", " ".join(command), flush=True)
        subprocess.run([sys.executable, "-m", *command], check=True)


if __name__ == "__main__":
    main()
