"""Comprehensive unit tests for the CAPA Report Generator.

Tests cover:
1. Deviation clustering (same site + same type + 30-day window)
2. CAPA generation with all required fields populated
3. LLM narrative boundary (only 3 fields go through LLM)
4. Markdown export correctness
5. PDF export produces valid PDF bytes
6. MockLLMClient CAPA narrative method

All tests use MockLLMClient or no LLM — no network access required.
No database required — tests operate on dicts and ORM instances directly.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from src.backend.capa.generator import (
    cluster_deviations,
    generate_capa_report,
    generate_capa_reports_for_site,
    _build_finding_summary,
    _pick_highest_severity,
    CLUSTER_WINDOW_DAYS,
)
from src.backend.capa.export import export_capa_markdown, export_capa_pdf
from src.backend.llm_client import MockLLMClient, _capa_narrative_fallback
from src.backend.models.capa import CAPAReport


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_deviation(
    dev_type: str = "missed_visit",
    site_id: str = "SITE-101",
    deviation_id: str = "DEV-0001",
    severity: str = "minor",
    severity_rationale: str = "Test rationale citing ICH E6(R2).",
    detected_at: Any = None,
    evidence: Any = None,
) -> Dict[str, Any]:
    """Construct a minimal deviation dict for CAPA generator tests.

    Args:
        dev_type: Deviation type string.
        site_id: Site identifier.
        deviation_id: Deviation primary key.
        severity: Final severity level.
        severity_rationale: Severity rationale text.
        detected_at: Detection timestamp (date or datetime).
        evidence: Structured evidence dict.

    Returns:
        Deviation dictionary suitable for cluster_deviations / generate_capa_report.
    """
    return {
        "deviation_id": deviation_id,
        "site_id": site_id,
        "type": dev_type,
        "severity": severity,
        "final_severity": severity,
        "severity_rationale": severity_rationale,
        "evidence": evidence or {"field": "actual_date", "expected": {}, "actual": None, "delta": {}},
        "detected_at": detected_at or datetime(2026, 9, 1, 10, 0, 0),
    }


def _make_capa_dict() -> Dict[str, Any]:
    """Construct a minimal CAPA dict for export tests.

    Returns:
        Dictionary matching CAPAReport field structure.
    """
    return {
        "capa_id": "CAPA-101-001",
        "deviation_ids": ["DEV-0001", "DEV-0002"],
        "finding": "2 deviations of type 'missed_visit' at site SITE-101 between 2026-09-01 and 2026-09-15. Highest severity: minor.",
        "severity": "minor",
        "severity_rationale": "Test rationale",
        "root_cause": "Scheduling gaps led to missed visits.",
        "corrective_action": "Retrain staff on visit scheduling.",
        "preventive_action": "Deploy automated visit reminders.",
        "owner": "Dr. Smith",
        "due_date": "2026-10-15",
        "status": "open",
    }


# ---------------------------------------------------------------------------
# 1. Clustering tests
# ---------------------------------------------------------------------------

class TestClustering:
    """Tests for the deviation clustering logic."""

    def test_same_site_same_type_within_window_single_cluster(self):
        """Deviations at same site + same type within 30 days → one cluster."""
        devs = [
            _make_deviation(detected_at=datetime(2026, 9, 1)),
            _make_deviation(detected_at=datetime(2026, 9, 10), deviation_id="DEV-0002"),
            _make_deviation(detected_at=datetime(2026, 9, 25), deviation_id="DEV-0003"),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_different_sites_separate_clusters(self):
        """Deviations at different sites → separate clusters."""
        devs = [
            _make_deviation(site_id="SITE-101"),
            _make_deviation(site_id="SITE-102", deviation_id="DEV-0002"),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 2

    def test_different_types_same_site_separate_clusters(self):
        """Different deviation types at same site → separate clusters."""
        devs = [
            _make_deviation(dev_type="missed_visit"),
            _make_deviation(dev_type="wrong_dose", deviation_id="DEV-0002"),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 2

    def test_exceeds_30_day_window_splits_cluster(self):
        """Deviations >30 days apart → separate clusters even if same site+type."""
        devs = [
            _make_deviation(detected_at=datetime(2026, 1, 1), deviation_id="DEV-0001"),
            _make_deviation(detected_at=datetime(2026, 1, 15), deviation_id="DEV-0002"),
            _make_deviation(detected_at=datetime(2026, 3, 15), deviation_id="DEV-0003"),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 2
        assert len(clusters[0]) == 2  # Jan 1 + Jan 15
        assert len(clusters[1]) == 1  # Mar 15

    def test_exactly_30_days_stays_in_cluster(self):
        """Deviation exactly 30 days from cluster start stays in the same cluster."""
        base = datetime(2026, 9, 1)
        devs = [
            _make_deviation(detected_at=base, deviation_id="DEV-0001"),
            _make_deviation(
                detected_at=base + timedelta(days=CLUSTER_WINDOW_DAYS),
                deviation_id="DEV-0002",
            ),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_31_days_creates_new_cluster(self):
        """Deviation 31 days from cluster start → new cluster."""
        base = datetime(2026, 9, 1)
        devs = [
            _make_deviation(detected_at=base, deviation_id="DEV-0001"),
            _make_deviation(
                detected_at=base + timedelta(days=CLUSTER_WINDOW_DAYS + 1),
                deviation_id="DEV-0002",
            ),
        ]
        clusters = cluster_deviations(devs)
        assert len(clusters) == 2

    def test_empty_deviations_returns_empty(self):
        """No deviations → no clusters."""
        assert cluster_deviations([]) == []

    def test_single_deviation_returns_single_cluster(self):
        """One deviation → one cluster of one."""
        clusters = cluster_deviations([_make_deviation()])
        assert len(clusters) == 1
        assert len(clusters[0]) == 1

    def test_multiple_sites_multiple_types_complex(self):
        """Complex scenario: 2 sites × 2 types with interleaved dates."""
        devs = [
            _make_deviation(site_id="SITE-101", dev_type="missed_visit", deviation_id="D1",
                            detected_at=datetime(2026, 9, 1)),
            _make_deviation(site_id="SITE-101", dev_type="wrong_dose", deviation_id="D2",
                            detected_at=datetime(2026, 9, 2)),
            _make_deviation(site_id="SITE-102", dev_type="missed_visit", deviation_id="D3",
                            detected_at=datetime(2026, 9, 3)),
            _make_deviation(site_id="SITE-101", dev_type="missed_visit", deviation_id="D4",
                            detected_at=datetime(2026, 9, 10)),
            _make_deviation(site_id="SITE-102", dev_type="missed_visit", deviation_id="D5",
                            detected_at=datetime(2026, 9, 15)),
        ]
        clusters = cluster_deviations(devs)
        # Expected: 3 clusters
        # (SITE-101, missed_visit): D1 + D4
        # (SITE-101, wrong_dose): D2
        # (SITE-102, missed_visit): D3 + D5
        assert len(clusters) == 3


# ---------------------------------------------------------------------------
# 2. CAPA generation tests
# ---------------------------------------------------------------------------

class TestCapaGeneration:
    """Tests for CAPA report generation with all required fields."""

    def test_single_deviation_produces_capa_with_all_fields(self):
        """A single deviation generates a CAPA with every required field populated."""
        dev = _make_deviation()
        report = generate_capa_report([dev], llm_client=None)

        assert isinstance(report, CAPAReport)
        assert report.capa_id is not None and report.capa_id != ""
        assert report.deviation_ids == ["DEV-0001"]
        assert report.finding != ""
        assert report.severity in ("major", "minor", "administrative")
        assert report.severity_rationale != ""
        assert report.root_cause != ""
        assert report.corrective_action != ""
        assert report.preventive_action != ""
        assert report.owner == "Unassigned"
        assert report.due_date is not None
        assert report.status == "open"

    def test_cluster_of_three_produces_single_capa(self):
        """Three deviations in one cluster → one CAPA with all deviation IDs."""
        devs = [
            _make_deviation(deviation_id="DEV-0001"),
            _make_deviation(deviation_id="DEV-0002",
                            detected_at=datetime(2026, 9, 5)),
            _make_deviation(deviation_id="DEV-0003",
                            detected_at=datetime(2026, 9, 10)),
        ]
        report = generate_capa_report(devs, llm_client=None)

        assert len(report.deviation_ids) == 3
        assert "DEV-0001" in report.deviation_ids
        assert "DEV-0002" in report.deviation_ids
        assert "DEV-0003" in report.deviation_ids

    def test_severity_is_highest_in_cluster(self):
        """CAPA severity equals the highest severity in the cluster."""
        devs = [
            _make_deviation(severity="administrative", deviation_id="D1"),
            _make_deviation(severity="major", deviation_id="D2"),
            _make_deviation(severity="minor", deviation_id="D3"),
        ]
        report = generate_capa_report(devs, llm_client=None)
        assert report.severity == "major"

    def test_finding_is_deterministic_text(self):
        """Finding summary is deterministic, not LLM-generated."""
        dev = _make_deviation(
            dev_type="wrong_dose",
            site_id="SITE-202",
            detected_at=datetime(2026, 8, 1),
        )
        report = generate_capa_report([dev], llm_client=None)

        assert "wrong_dose" in report.finding
        assert "SITE-202" in report.finding
        assert "2026-08-01" in report.finding

    def test_default_due_date_is_30_days(self):
        """Due date defaults to 30 days from today."""
        report = generate_capa_report([_make_deviation()], llm_client=None)
        expected = date.today() + timedelta(days=30)
        assert report.due_date == expected

    def test_custom_owner_and_due_date(self):
        """Owner and due_date can be explicitly set."""
        custom_date = date(2027, 1, 1)
        report = generate_capa_report(
            [_make_deviation()],
            llm_client=None,
            owner="Dr. Johnson",
            due_date=custom_date,
        )
        assert report.owner == "Dr. Johnson"
        assert report.due_date == custom_date

    def test_empty_cluster_raises_error(self):
        """Empty cluster raises ValueError."""
        try:
            generate_capa_report([], llm_client=None)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "empty" in str(e).lower()

    def test_generate_reports_for_site_auto_ids(self):
        """generate_capa_reports_for_site assigns sequential IDs."""
        devs = [
            _make_deviation(dev_type="missed_visit", deviation_id="D1",
                            detected_at=datetime(2026, 9, 1)),
            _make_deviation(dev_type="wrong_dose", deviation_id="D2",
                            detected_at=datetime(2026, 9, 5)),
        ]
        reports = generate_capa_reports_for_site(devs, llm_client=None)
        assert len(reports) == 2
        ids = [r.capa_id for r in reports]
        assert all(id_.startswith("CAPA-101-") for id_ in ids)


# ---------------------------------------------------------------------------
# 3. LLM narrative field tests
# ---------------------------------------------------------------------------

class TestLLMNarrativeFields:
    """Tests verifying the LLM boundary — only three fields are LLM-authored."""

    def test_with_mock_llm_narratives_populated(self):
        """MockLLMClient produces non-empty root_cause, corrective_action, preventive_action."""
        mock_llm = MockLLMClient()
        dev = _make_deviation(dev_type="missed_visit")
        report = generate_capa_report([dev], llm_client=mock_llm)

        assert report.root_cause != ""
        assert report.corrective_action != ""
        assert report.preventive_action != ""

    def test_without_llm_fallback_narratives_used(self):
        """When llm_client=None, deterministic fallback text is used."""
        dev = _make_deviation(dev_type="banned_comed")
        report = generate_capa_report([dev], llm_client=None)

        # Should have the canned banned_comed narrative
        assert "concomitant medication" in report.root_cause.lower()
        assert report.corrective_action != ""
        assert report.preventive_action != ""

    def test_narratives_differ_by_type(self):
        """Different deviation types produce different fallback narratives."""
        report_missed = generate_capa_report(
            [_make_deviation(dev_type="missed_visit")], llm_client=None
        )
        report_dose = generate_capa_report(
            [_make_deviation(dev_type="wrong_dose")], llm_client=None
        )

        assert report_missed.root_cause != report_dose.root_cause

    def test_finding_not_llm_generated(self):
        """The finding field must be deterministic, never from the LLM."""
        mock_llm = MockLLMClient()
        dev = _make_deviation(dev_type="missed_visit", site_id="SITE-101")
        report = generate_capa_report([dev], llm_client=mock_llm)

        # Finding should contain site ID and type (deterministic format)
        assert "SITE-101" in report.finding
        assert "missed_visit" in report.finding


# ---------------------------------------------------------------------------
# 4. Markdown export tests
# ---------------------------------------------------------------------------

class TestExportMarkdown:
    """Tests for Markdown export of CAPA reports."""

    def test_markdown_contains_all_sections(self):
        """Markdown output includes all required section headings."""
        capa = _make_capa_dict()
        md = export_capa_markdown(capa)

        assert "# CAPA Report:" in md
        assert "## Finding" in md
        assert "## Severity" in md
        assert "## Root Cause Analysis" in md
        assert "## Corrective Action" in md
        assert "## Preventive Action" in md
        assert "## Assignment" in md

    def test_markdown_contains_field_values(self):
        """Markdown output includes actual field values from the CAPA."""
        capa = _make_capa_dict()
        md = export_capa_markdown(capa)

        assert "CAPA-101-001" in md
        assert "DEV-0001" in md
        assert "DEV-0002" in md
        assert "Dr. Smith" in md
        assert "2026-10-15" in md
        assert "open" in md
        assert "Scheduling gaps" in md

    def test_markdown_from_orm_instance(self):
        """Export works with a CAPAReport ORM instance, not just dicts."""
        report = generate_capa_report(
            [_make_deviation()], llm_client=None, owner="Test Owner"
        )
        md = export_capa_markdown(report)

        assert "CAPA Report:" in md
        assert "Test Owner" in md
        assert "## Finding" in md


# ---------------------------------------------------------------------------
# 5. PDF export tests
# ---------------------------------------------------------------------------

class TestExportPDF:
    """Tests for PDF export of CAPA reports."""

    def test_pdf_returns_bytes(self):
        """PDF export returns a bytes object."""
        capa = _make_capa_dict()
        pdf_bytes = export_capa_pdf(capa)
        assert isinstance(pdf_bytes, bytes)

    def test_pdf_starts_with_pdf_header(self):
        """Valid PDF files start with '%PDF'."""
        capa = _make_capa_dict()
        pdf_bytes = export_capa_pdf(capa)
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_is_non_empty(self):
        """PDF output has substantial content."""
        capa = _make_capa_dict()
        pdf_bytes = export_capa_pdf(capa)
        # A minimal PDF with sections should be at least a few KB
        assert len(pdf_bytes) > 100

    def test_pdf_from_orm_instance(self):
        """Export works with a CAPAReport ORM instance."""
        report = generate_capa_report(
            [_make_deviation()], llm_client=None
        )
        pdf_bytes = export_capa_pdf(report)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 100


# ---------------------------------------------------------------------------
# 6. MockLLMClient CAPA narrative tests
# ---------------------------------------------------------------------------

class TestMockLLMCapaNarrative:
    """Tests for MockLLMClient.generate_capa_narrative method."""

    def test_returns_dict_with_three_keys(self):
        """MockLLMClient returns dict with exactly root_cause, corrective_action, preventive_action."""
        mock_llm = MockLLMClient()
        summaries = [{"type": "missed_visit", "severity": "minor",
                       "severity_rationale": "Test", "evidence": {}}]
        result = mock_llm.generate_capa_narrative(summaries)

        assert isinstance(result, dict)
        assert "root_cause" in result
        assert "corrective_action" in result
        assert "preventive_action" in result
        assert len(result) == 3

    def test_all_values_non_empty(self):
        """All three narrative values are non-empty strings."""
        mock_llm = MockLLMClient()
        summaries = [{"type": "wrong_dose", "severity": "major",
                       "severity_rationale": "Test", "evidence": {}}]
        result = mock_llm.generate_capa_narrative(summaries)

        for key in ("root_cause", "corrective_action", "preventive_action"):
            assert isinstance(result[key], str)
            assert len(result[key]) > 10, f"'{key}' should be a substantial string"

    def test_narratives_keyed_on_type(self):
        """Different deviation types produce different narratives."""
        mock_llm = MockLLMClient()

        result_visit = mock_llm.generate_capa_narrative(
            [{"type": "missed_visit", "severity": "minor", "severity_rationale": "", "evidence": {}}]
        )
        result_dose = mock_llm.generate_capa_narrative(
            [{"type": "wrong_dose", "severity": "minor", "severity_rationale": "", "evidence": {}}]
        )

        assert result_visit["root_cause"] != result_dose["root_cause"]

    def test_unknown_type_uses_default_fallback(self):
        """Unknown deviation type uses the default fallback narrative."""
        mock_llm = MockLLMClient()
        result = mock_llm.generate_capa_narrative(
            [{"type": "unknown_xyz", "severity": "minor", "severity_rationale": "", "evidence": {}}]
        )
        assert "root_cause" in result
        assert result["root_cause"] != ""

    def test_empty_summaries_uses_default(self):
        """Empty summaries list uses default fallback without crashing."""
        mock_llm = MockLLMClient()
        result = mock_llm.generate_capa_narrative([])
        assert "root_cause" in result


# ---------------------------------------------------------------------------
# 7. Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    """Tests for internal helper functions."""

    def test_pick_highest_severity_major_wins(self):
        """Major severity outranks minor and administrative."""
        devs = [
            _make_deviation(severity="minor"),
            _make_deviation(severity="major", deviation_id="D2"),
            _make_deviation(severity="administrative", deviation_id="D3"),
        ]
        sev, rationale = _pick_highest_severity(devs)
        assert sev == "major"

    def test_pick_highest_severity_minor_over_admin(self):
        """Minor outranks administrative."""
        devs = [
            _make_deviation(severity="administrative"),
            _make_deviation(severity="minor", deviation_id="D2"),
        ]
        sev, _ = _pick_highest_severity(devs)
        assert sev == "minor"

    def test_pick_highest_severity_single_admin(self):
        """Single administrative deviation → administrative."""
        sev, _ = _pick_highest_severity([_make_deviation(severity="administrative")])
        assert sev == "administrative"

    def test_build_finding_summary_format(self):
        """Finding summary has expected format with count, type, site, dates."""
        devs = [
            _make_deviation(detected_at=datetime(2026, 9, 1)),
            _make_deviation(detected_at=datetime(2026, 9, 15), deviation_id="D2"),
        ]
        summary = _build_finding_summary(devs)

        assert "2 deviations" in summary
        assert "missed_visit" in summary
        assert "SITE-101" in summary
        assert "2026-09-01" in summary
        assert "2026-09-15" in summary

    def test_build_finding_summary_single(self):
        """Single deviation uses singular noun."""
        summary = _build_finding_summary([_make_deviation()])
        assert "1 deviation " in summary

    def test_capa_narrative_fallback_missed_visit(self):
        """Fallback narrative for missed_visit mentions scheduling."""
        result = _capa_narrative_fallback([{"type": "missed_visit"}])
        assert "scheduling" in result["root_cause"].lower() or "visit" in result["root_cause"].lower()

    def test_capa_narrative_fallback_empty_list(self):
        """Empty list uses default fallback."""
        result = _capa_narrative_fallback([])
        assert result["root_cause"] != ""
        assert result["corrective_action"] != ""
        assert result["preventive_action"] != ""
