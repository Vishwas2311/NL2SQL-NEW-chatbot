"""Run the optional Strix assessment on a disposable, sanitized source snapshot."""

import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast
from uuid import uuid4

from export_project_to_txt import OUTPUT_NAME, private_json, project_files

ROOT = Path(__file__).resolve().parents[1]
SCOPE = """Assess only the supplied NL2SQL source and synthetic instances you create inside the sandbox.
Review the full backend: bearer/JWT identity, tenant/region/metric grants, session ownership,
SQL injection, compiler/validator capability tampering, metadata signatures/publication/rollback,
provider egress/SSRF, resource limits, and safe API errors. Use the existing synthetic tests and fakes.
The supplied UI assets are frozen reference files; inspect them but do not modify them.
Do not connect to company Oracle, real model/embedding endpoints, or third-party scan targets.
Do not download model weights, publish code, deploy, send messages, or change the host project.
Use only synthetic test credentials generated in your sandbox. Report proven issues separately from
unconfirmed observations. State untested paths and any budget/turn limits in the final report.
"""


def prepare_source(root: Path, destination: Path) -> int:
    """Reuse the exporter's private-file rules and preserve every included file byte for byte."""
    destination.mkdir(parents=True, exist_ok=False)
    total = count = 0
    for source in project_files(root, root / OUTPUT_NAME):
        with source.open("rb") as stream:
            payload = stream.read(25_000_001)
        total += len(payload)
        if total > 25_000_000:
            raise ValueError("Sanitized source exceeds the 25 MB scan budget")
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        if "\x00" in text or private_json(text):
            continue
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        count += 1
    return count


def scan_complete(run: Path) -> bool:
    """A zero process exit alone cannot establish that a bounded scan completed."""
    records = tuple((run / "strix_runs").glob("*/run.json"))
    if len(records) != 1:
        return False
    try:
        record: object = json.loads(records[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and cast(dict[str, object], record).get("status") == "completed"


def main() -> int:
    """Manual only: the scanner's model connection must already be configured locally."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="Prepare without running Strix")
    parser.add_argument("--max-budget", type=float, default=10, help="LLM spending cap in USD")
    default = shutil.which("strix") or str(
        Path.home() / ".codex/tools/strix-1.7.0/Scripts/strix.exe"
    )
    parser.add_argument(
        "--strix", type=Path, default=Path(default), help="Installed Strix executable"
    )
    args = parser.parse_args()
    if not math.isfinite(args.max_budget) or args.max_budget <= 0:
        parser.error("--max-budget must be a finite positive number")
    if not args.prepare_only and not args.strix.is_file():
        parser.error("Install Strix separately or supply its executable with --strix")
    run = ROOT / ".local/strix" / uuid4().hex
    count = prepare_source(ROOT, run / "source")
    instructions = run / "scope.txt"
    instructions.write_text(SCOPE, encoding="utf-8")
    print(f"Prepared {count} source files. Scan workspace: {run}", flush=True)
    if args.prepare_only:
        return 0
    result = subprocess.run(
        [
            str(args.strix.resolve()),
            "-n",
            "-t",
            str(run / "source"),
            "--scope-mode",
            "full",
            "--scan-mode",
            "standard",
            "--max-budget",
            str(args.max_budget),
            "--instruction-file",
            str(instructions),
        ],
        cwd=run,
        env={**os.environ, "STRIX_TELEMETRY": "0"},
        check=False,
    )
    if result.returncode:
        return result.returncode
    if not scan_complete(run):
        print("Strix did not record a completed scan. Review the run artifacts before retrying.")
        return 1
    print(f"Strix finished. Review {run / 'strix_runs'} for findings, cost and coverage limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
