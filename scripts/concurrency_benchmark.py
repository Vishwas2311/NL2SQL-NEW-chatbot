"""Record local 1/10/25/50-caller measurements without contacting external services."""

import json
import tempfile
from pathlib import Path

from nl2sql.evaluation.load import evaluate_load


def main() -> None:
    """Write repeatable evidence; preserve the original UI and design pack."""
    with tempfile.TemporaryDirectory(prefix="nl2sql-load-") as directory:
        report = evaluate_load(Path(directory) / "latency", trace_memory=False)
        report["memory_profile_separate_run"] = evaluate_load(Path(directory) / "memory")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/concurrency.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
