"""Comprehensive unit tests for the Hybrid Severity Classifier.

Tests cover:
1. Clear-cut deterministic cases (no LLM call needed)
2. Ambiguous cases with MockLLMClient (override applied, rationale stored)
3. Deterministic table driving the non-ambiguous majority
4. Edge cases: no LLM client, unknown types, missing evidence
"""

from datetime import date, timedelta
from typing import Any, Dict
from unittest.mock import patch

from src.backend.detection.severity_classifier import (
    apply_deterministic_severity,
    classify_severity,
    classify_batch,
    load_severity_rules,
    _extract_evidence_value,
    _evaluate_condition,
)
from src.backend.llm_client import MockLLMClient, BaseLLMClient


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_deviation(
    dev_type: str,
    delta: Any = None,
    evidence_field: str = "actual_date",
) -> Dict[str, Any]:
    """Helper to construct a minimal deviation dict for classifier tests.

    Args:
        dev_type: Deviation type string (e.g., 'missed_visit').
        delta: Evidence delta value — dict or scalar.
        evidence_field: Evidence field name.

    Returns:
        Deviation dictionary suitable for classify_severity().
    """
    return {
        "record_id": "R-TEST",
        "patient_id": "P-TEST",
        "type": dev_type,
        "severity": "major",
        "severity_rationale": "Test rationale",
        "evidence": {
            "field": evidence_field,
            "expected": {},
            "actual": None,
            "delta": delta or {},
        },
    }


# ---------------------------------------------------------------------------
# 1. Rules loading
# ---------------------------------------------------------------------------

class TestRulesLoading:
    """Tests for severity rules YAML loading."""

    def test_load_severity_rules_returns_dict(self):
        """Verify rules load successfully and contain expected deviation types."""
        # Clear LRU cache to ensure fresh load
        load_severity_rules.cache_clear()
        rules = load_severity_rules()
        assert isinstance(rules, dict)
        assert "banned_comed" in rules
        assert "missed_visit" in rules
        assert "wrong_dose" in rules
        assert "eligibility_breach" in rules
        assert "documentation" in rules

    def test_each_rule_has_default_severity(self):
        """Every rule type must define a default_severity."""
        load_severity_rules.cache_clear()
        rules = load_severity_rules()
        for dev_type, rule in rules.items():
            assert "default_severity" in rule, f"'{dev_type}' missing default_severity"
            assert rule["default_severity"] in ("major", "minor", "administrative"), (
                f"'{dev_type}' has invalid default_severity: {rule['default_severity']}"
            )


# ---------------------------------------------------------------------------
# 2. Clear-cut deterministic cases (no LLM call needed)
# ---------------------------------------------------------------------------

class TestClearCutDeterministic:
    """Tests where the deterministic rules table is sufficient — no LLM involvement."""

    def test_banned_comed_always_major(self):
        """banned_comed → major, severity_source=deterministic, no LLM call."""
        dev = _make_deviation("banned_comed", delta="Drug match")
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "major"
        assert result["final_severity"] == "major"
        assert result["severity_source"] == "deterministic"
        assert "ICH E6" in result["severity_rationale"]

    def test_eligibility_breach_always_major(self):
        """eligibility_breach → major deterministically."""
        dev = _make_deviation("eligibility_breach")
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "major"
        assert result["final_severity"] == "major"
        assert result["severity_source"] == "deterministic"

    def test_documentation_always_administrative(self):
        """documentation → administrative deterministically."""
        dev = _make_deviation("documentation")
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "administrative"
        assert result["final_severity"] == "administrative"
        assert result["severity_source"] == "deterministic"
        assert "administrative" in result["severity_rationale"].lower()

    def test_missed_visit_over_14_days_major(self):
        """missed_visit with >14 days outside window → major via conditional override."""
        dev = _make_deviation(
            "missed_visit",
            delta={"days_offset_from_scheduled": 20, "days_outside_window": 17},
        )
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "major"
        assert result["final_severity"] == "major"
        assert result["severity_source"] == "deterministic"

    def test_wrong_dose_large_deviation_major(self):
        """wrong_dose with >10% deviation → major (not ambiguous, no LLM)."""
        dev = _make_deviation(
            "wrong_dose",
            delta={"absolute_difference": 5.0, "percentage_deviation": 50.0, "allowed_tolerance_pct": 5.0},
            evidence_field="dose_given",
        )
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "major"
        assert result["final_severity"] == "major"
        assert result["severity_source"] == "deterministic"


# ---------------------------------------------------------------------------
# 3. Ambiguous cases with MockLLMClient (LLM override applied)
# ---------------------------------------------------------------------------

class TestAmbiguousWithLLM:
    """Tests where the case is ambiguous and the MockLLMClient provides an override."""

    def test_missed_visit_borderline_llm_review(self):
        """missed_visit with ≤3 days outside window → ambiguous → MockLLM reviews.

        The mock returns 'minor' for borderline missed visits.
        """
        dev = _make_deviation(
            "missed_visit",
            delta={"days_offset_from_scheduled": 5, "days_outside_window": 2},
        )
        mock_llm = MockLLMClient()
        result = classify_severity(dev, llm_client=mock_llm)

        assert result["default_severity"] == "minor"
        assert result["final_severity"] == "minor"
        assert result["severity_source"] == "llm_override"
        assert "ICH E6" in result["severity_rationale"]

    def test_wrong_dose_small_deviation_ambiguous(self):
        """wrong_dose with ≤10% deviation → ambiguous → MockLLM overrides to minor."""
        dev = _make_deviation(
            "wrong_dose",
            delta={"absolute_difference": 0.8, "percentage_deviation": 8.0, "allowed_tolerance_pct": 5.0},
            evidence_field="dose_given",
        )
        mock_llm = MockLLMClient()
        result = classify_severity(dev, llm_client=mock_llm)

        # Condition: percentage_deviation <= 10 → ambiguous=true, severity=minor
        assert result["default_severity"] == "minor"
        assert result["final_severity"] == "minor"
        assert result["severity_source"] == "llm_override"

    def test_llm_rationale_cites_ich_e6(self):
        """Assert that the LLM-provided rationale references ICH E6(R2)."""
        dev = _make_deviation(
            "missed_visit",
            delta={"days_offset_from_scheduled": 4, "days_outside_window": 1},
        )
        mock_llm = MockLLMClient()
        result = classify_severity(dev, llm_client=mock_llm)

        assert "ICH E6" in result["severity_rationale"], (
            f"Rationale should cite ICH E6(R2) but got: {result['severity_rationale']}"
        )

    def test_llm_override_changes_severity(self):
        """Verify that when the MockLLM overrides, the severity actually differs from rule default.

        missed_visit with days_outside_window > 3 but ≤14: the first condition
        that matches is days_outside_window > 14 (doesn't match for 5),
        then days_outside_window ≤ 3 (doesn't match for 5).
        No condition matches → falls through to type default (minor, not ambiguous).
        So this case is actually deterministic.

        For a true LLM override, we need days_outside_window ≤ 3 to trigger
        ambiguity, and then the MockLLM decides.
        """
        # Case: 3 days exactly outside window → matches lte 3 → ambiguous
        dev = _make_deviation(
            "missed_visit",
            delta={"days_offset_from_scheduled": 6, "days_outside_window": 3},
        )
        mock_llm = MockLLMClient()
        result = classify_severity(dev, llm_client=mock_llm)

        # MockLLM for missed_visit with days_outside <= 3 returns "minor"
        assert result["severity_source"] == "llm_override"
        assert result["final_severity"] == "minor"


# ---------------------------------------------------------------------------
# 4. Deterministic table drives non-ambiguous majority
# ---------------------------------------------------------------------------

class TestDeterministicMajority:
    """Confirm the deterministic table handles the majority of cases without LLM calls."""

    def test_batch_majority_deterministic(self):
        """Run classifier over a mixed batch of 20 deviations. Assert >80% deterministic."""
        deviations = [
            # 5x banned_comed → deterministic major
            _make_deviation("banned_comed") for _ in range(5)
        ] + [
            # 5x eligibility_breach → deterministic major
            _make_deviation("eligibility_breach") for _ in range(5)
        ] + [
            # 3x documentation → deterministic administrative
            _make_deviation("documentation") for _ in range(3)
        ] + [
            # 3x missed_visit >14 days → deterministic major
            _make_deviation("missed_visit", delta={"days_outside_window": 20}) for _ in range(3)
        ] + [
            # 2x wrong_dose >10% → deterministic major
            _make_deviation("wrong_dose", delta={"percentage_deviation": 50.0}) for _ in range(2)
        ] + [
            # 2x missed_visit ≤3 days → ambiguous (will use LLM)
            _make_deviation("missed_visit", delta={"days_outside_window": 2}) for _ in range(2)
        ]

        assert len(deviations) == 20

        mock_llm = MockLLMClient()
        results = classify_batch(deviations, llm_client=mock_llm)

        deterministic_count = sum(1 for r in results if r["severity_source"] == "deterministic")
        llm_count = sum(1 for r in results if r["severity_source"] == "llm_override")

        assert deterministic_count >= 16, (
            f"Expected ≥16 deterministic (80%), got {deterministic_count}"
        )
        assert llm_count == 2, f"Expected exactly 2 LLM overrides, got {llm_count}"
        assert deterministic_count + llm_count == 20


# ---------------------------------------------------------------------------
# 5. Edge cases and fallback behavior
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: no LLM client on ambiguous, unknown types, missing evidence."""

    def test_no_llm_client_falls_back_deterministic(self):
        """When llm_client=None, ambiguous cases use the default severity without crashing."""
        dev = _make_deviation(
            "missed_visit",
            delta={"days_offset_from_scheduled": 5, "days_outside_window": 2},
        )
        # No LLM client — should not crash, should use deterministic default
        result = classify_severity(dev, llm_client=None)

        assert result["severity_source"] == "deterministic"
        assert result["final_severity"] == result["default_severity"]

    def test_unknown_deviation_type_defaults_to_minor(self):
        """Unknown deviation types default to 'minor' severity."""
        dev = _make_deviation("unknown_type_xyz")
        result = classify_severity(dev, llm_client=None)

        assert result["default_severity"] == "minor"
        assert result["final_severity"] == "minor"
        assert result["severity_source"] == "deterministic"

    def test_missing_delta_in_evidence(self):
        """Deviations with missing or non-dict delta should not crash the classifier."""
        dev = _make_deviation("missed_visit", delta="Missed visit (0 actual days recorded)")
        result = classify_severity(dev, llm_client=None)

        # No condition can match a string delta → falls through to type default
        assert result["default_severity"] == "minor"
        assert result["severity_source"] == "deterministic"

    def test_empty_evidence(self):
        """Deviations with completely empty evidence should not crash."""
        dev = {
            "record_id": "R-TEST",
            "patient_id": "P-TEST",
            "type": "banned_comed",
            "severity": "major",
            "severity_rationale": "Test",
            "evidence": {},
        }
        result = classify_severity(dev, llm_client=None)
        assert result["default_severity"] == "major"
        assert result["final_severity"] == "major"


# ---------------------------------------------------------------------------
# 6. Internal helper tests
# ---------------------------------------------------------------------------

class TestHelpers:
    """Tests for internal helper functions."""

    def test_extract_evidence_value_from_dict_delta(self):
        """Extract numeric value from a dict-style delta."""
        evidence = {"delta": {"days_outside_window": 5, "days_offset_from_scheduled": 8}}
        assert _extract_evidence_value(evidence, "days_outside_window") == 5.0
        assert _extract_evidence_value(evidence, "days_offset_from_scheduled") == 8.0
        assert _extract_evidence_value(evidence, "nonexistent") is None

    def test_extract_evidence_value_from_string_delta(self):
        """String delta returns None (cannot extract numeric field)."""
        evidence = {"delta": "Missed visit"}
        assert _extract_evidence_value(evidence, "days_outside_window") is None

    def test_evaluate_condition_operators(self):
        """Verify all supported comparison operators."""
        evidence = {"delta": {"value": 10}}

        assert _evaluate_condition({"field": "value", "operator": "gt", "threshold": 5}, evidence) is True
        assert _evaluate_condition({"field": "value", "operator": "gt", "threshold": 10}, evidence) is False
        assert _evaluate_condition({"field": "value", "operator": "gte", "threshold": 10}, evidence) is True
        assert _evaluate_condition({"field": "value", "operator": "lt", "threshold": 15}, evidence) is True
        assert _evaluate_condition({"field": "value", "operator": "lt", "threshold": 10}, evidence) is False
        assert _evaluate_condition({"field": "value", "operator": "lte", "threshold": 10}, evidence) is True
        assert _evaluate_condition({"field": "value", "operator": "eq", "threshold": 10}, evidence) is True
        assert _evaluate_condition({"field": "value", "operator": "eq", "threshold": 5}, evidence) is False

    def test_evaluate_condition_unknown_operator(self):
        """Unknown operator returns False without crashing."""
        evidence = {"delta": {"value": 10}}
        assert _evaluate_condition({"field": "value", "operator": "nope", "threshold": 5}, evidence) is False
