"""Run the same mandatory backend gates locally and in CI."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


def main() -> None:
    """Fail fast; a skipped command is never recorded as passing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--redis-env", type=Path, help="Explicit isolated loopback Redis test environment"
    )
    arguments = parser.parse_args()
    if arguments.redis_env is not None:
        values = dotenv_values(arguments.redis_env)
        url = values.get("NL2SQL_TEST_REDIS_URL")
        if (
            set(values) != {"NL2SQL_TEST_REDIS_URL"}
            or not url
            or urlparse(url).scheme not in {"redis", "rediss"}
            or urlparse(url).hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            parser.error("Select a test-only environment containing one loopback Redis test URL")
        os.environ["NL2SQL_TEST_REDIS_URL"] = url
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
