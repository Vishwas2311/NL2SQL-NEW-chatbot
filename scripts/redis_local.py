"""Prepare isolated synthetic Redis ACLs and environment files without replacing secrets."""

import hashlib
import secrets
from pathlib import Path


def prepare(root: Path) -> Path:
    """Keep repeat runs stable; refuse a partial setup instead of rotating a running service."""
    directory = root / ".local" / "redis"
    directory.mkdir(parents=True, exist_ok=True)
    paths = tuple(directory / name for name in ("users.acl", "local.env", "test.env"))
    if any(path.exists() for path in paths):
        if not all(path.is_file() for path in paths):
            raise ValueError("Partial local Redis setup; restore the files before continuing.")
    else:
        application_password, test_password = (secrets.token_hex(32) for _ in range(2))
        commands = "+ping +eval +time +zremrangebyscore +zcard +zadd +pexpire +zscore +zrem +client|setinfo +client|setname"
        acl = (
            "user default off\n"
            f"user nl2sql on #{hashlib.sha256(application_password.encode()).hexdigest()} "
            f"~ews:nl2sql:local:* {commands}\n"
            f"user nl2sql_test on #{hashlib.sha256(test_password.encode()).hexdigest()} "
            f"~ews:test:* {commands} +del +pttl +zrange\n"
        )
        application_env = (
            "# Generated synthetic local Redis settings; never use for office credentials.\n"
            "NL2SQL_DATA_CLASSIFICATION=synthetic\nNL2SQL_QUERY_BACKEND=sqlite\n"
            "NL2SQL_MODEL_MODE=disabled\nNL2SQL_EMBEDDING_MODE=disabled\n"
            "NL2SQL_RATE_LIMIT_BACKEND=redis\nNL2SQL_API_WORKERS=2\n"
            f"NL2SQL_REDIS_URL=redis://nl2sql:{application_password}@127.0.0.1:6380/0\n"
            "NL2SQL_REDIS_KEY_PREFIX=ews:nl2sql:local\n"
            "NL2SQL_REDIS_TIMEOUT_SECONDS=0.5\nNL2SQL_REDIS_MAX_CONNECTIONS=16\n"
            "NL2SQL_REQUESTS_PER_MINUTE=60\nNL2SQL_HTTP_CONCURRENCY_LIMIT=64\n"
            "NL2SQL_MAX_CONCURRENT_CHATS=8\nNL2SQL_MAX_CONCURRENT_CHATS_PER_PRINCIPAL=1\n"
            "NL2SQL_ADMISSION_LEASE_SECONDS=300\n"
        )
        test_env = (
            "# Isolated loopback test identity; never use the office Redis URL here.\n"
            f"NL2SQL_TEST_REDIS_URL=redis://nl2sql_test:{test_password}@127.0.0.1:6380/0\n"
        )
        for path, content in zip(paths, (acl, application_env, test_env), strict=True):
            with path.open("x", encoding="utf-8", newline="\n") as destination:
                destination.write(content)
    try:
        with (root / ".env").open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(paths[1].read_text(encoding="utf-8"))
    except FileExistsError:
        pass
    return paths[1]


def main() -> None:
    """Generate files only: starting Redis remains an explicit local Docker command."""
    path = prepare(Path(__file__).resolve().parents[1])
    print(f"Local Redis settings prepared: {path}. Existing .env files were preserved.")


if __name__ == "__main__":
    main()
