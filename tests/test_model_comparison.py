"""The provider comparison seam runs authored fixtures without making network calls."""

import pytest
from nl2sql.evaluation import compare_models, golden_cases
from nl2sql.model import MockModel
from nl2sql.synthetic import synthetic_catalog


def test_model_comparison_uses_explicit_independent_provider_factories(tmp_path):
    cases = golden_cases(synthetic_catalog().version)
    plans = {case.question: case.draft.model_dump_json() for case in cases if case.draft}
    created = []

    def factory():
        provider = MockModel(dict(plans))
        created.append(provider)
        return provider

    result = compare_models(tmp_path / "runs", {"first": factory, "second": factory})
    assert len(created) == 2 and created[0] is not created[1]
    assert set(result["runs"]) == {"first", "second"}
    for run in result["runs"].values():
        assert run["passed"] == 46 and run["correct_results"] == 37
        assert run["provider"] == "injected_provider_unqualified"
    for factories in ({}, {str(index): factory for index in range(9)}):
        with pytest.raises(ValueError):
            compare_models(tmp_path / "invalid", factories)
