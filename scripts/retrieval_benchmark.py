"""Record the lexical baseline and the actual availability of optional hybrid evidence."""

import json
import tempfile
from pathlib import Path

from nl2sql.domain import Principal
from nl2sql.retrieval_evaluation import evaluate_retrieval
from nl2sql.retrieval_experiment import compare_retrieval
from nl2sql.synthetic import ALL_METRICS, synthetic_catalog


def main() -> None:
    """Use compare_retrieval with an injected approved encoder for a paired experiment."""
    with tempfile.TemporaryDirectory(prefix="ews-retrieval-") as directory:
        report = compare_retrieval(Path(directory))
        catalog = synthetic_catalog()
        principals = (
            Principal(id="analyst", tenant="demo", regions=("north", "south"), metrics=ALL_METRICS),
            Principal(id="north_analyst", tenant="demo", regions=("north",), metrics=ALL_METRICS),
        )
        report["retrieval_only"] = evaluate_retrieval(catalog, principals)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/retrieval.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["hybrid_status"])


if __name__ == "__main__":
    main()
