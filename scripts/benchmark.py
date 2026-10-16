"""Run diverse synthetic known-answer workflows; never label mocks as model accuracy."""

import json
import tempfile
from pathlib import Path

from nl2sql.evaluation import evaluate_workflows


def main() -> None:
    """Write all case outcomes and fail the command if any golden disagrees."""
    with tempfile.TemporaryDirectory(prefix="ews-benchmark-") as directory:
        report = evaluate_workflows(Path(directory))
    path = Path("reports/benchmark.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    if report["passed"] != report["runs"]:
        raise SystemExit("Workflow mismatches: inspect reports/benchmark.json")


if __name__ == "__main__":
    main()
