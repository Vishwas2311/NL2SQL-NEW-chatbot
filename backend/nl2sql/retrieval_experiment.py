"""Paired lexical/hybrid workflow experiment with identical questions and known answers."""

from pathlib import Path

from nl2sql.evaluation import evaluate_workflows
from nl2sql.retrieval import EmbeddingProvider


def compare_retrieval(
    root: Path, encoder: EmbeddingProvider | None = None, encoder_id: str | None = None
) -> dict[str, object]:
    """Caller supplies an approved encoder; this module downloads and installs nothing."""
    if encoder is not None and not encoder_id:
        raise ValueError("Record the approved encoder identity before comparing retrieval")
    lexical = evaluate_workflows(root / "lexical")
    hybrid = evaluate_workflows(root / "hybrid", encoder) if encoder is not None else None
    return {
        "lexical": lexical,
        "hybrid": hybrid,
        "encoder": encoder_id,
        "hybrid_status": "measured" if hybrid is not None else "not_run_no_approved_encoder",
        "method": (
            "Identical independent workflow goldens, plans, catalog and scope; fresh databases."
        ),
        "promotion_gate": "Compare business results and safe rejections "
        "before retrieval recall/latency. "
        "Exact aliases bypass vector search. Add held-out enterprise paraphrases before promotion.",
    }
