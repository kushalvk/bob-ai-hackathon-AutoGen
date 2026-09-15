"""Comprehensive unit and integration tests for the deterministic Site Risk Scoring Engine.

Validates:
1. Risk configuration loading, schema validation, and exact factor weights summing to 1.0 (100%).
2. Normalization functions across all 7 factors with boundary and edge case testing.
3. Pure mathematical scoring engine transparency and contribution summation.
4. Seeded database validation: planted high-risk site (SITE-101) scores highest,
   planted low-risk site (SITE-105) scores lowest, and risk ordering is verified.
5. FastAPI route execution and database persistence (/api/risk/compute and /api/risk/scores).
"""

import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

from src.backend.config import RISK_WEIGHTS_PATH
from src.backend.risk.config import (
    RiskConfig,
    FactorConfig,
    load_risk_config,
    EXPECTED_FACTORS,
)
from src.backend.risk.normalizers import (
    normalize_major_deviation_rate,
    normalize_minor_deviation_rate,
    normalize_deviation_trend,
    normalize_query_resolution_time,
    normalize_enrollment_target,
    normalize_staff_turnover,
    normalize_days_since_monitoring,
)
from src.backend.risk.engine import calculate_site_risk
from src.backend.risk.service import compute_and_persist_site_risk_scores
from src.backend.database import SessionLocal
from src.backend.models import Site, Deviation, Patient, SiteRiskScore
from src.backend.main import app
from src.backend.seed import run_seed


# ---------------------------------------------------------------------------
# 1. Config Validation Tests
# ---------------------------------------------------------------------------

def test_risk_weights_config_loading_and_factors():
    """Verify risk_weights.json loads correctly and contains all 7 required factors with exact weights."""
    config = load_risk_config()
    assert isinstance(config, RiskConfig)
    assert set(config.factors.keys()) == EXPECTED_FACTORS

    # Verify exact weights from prompt specification
    expected_weights = {
        "major_deviation_rate": 0.30,
        "minor_deviation_rate": 0.10,
        "deviation_trend": 0.15,
        "query_resolution_time": 0.15,
        "enrollment_vs_target": 0.10,
        "staff_turnover_rate": 0.10,
        "days_since_last_monitoring_visit": 0.10,
    }
    for factor, weight in expected_weights.items():
        assert config.factors[factor].weight == weight, f"Weight mismatch for {factor}"

    total_weight = sum(f.weight for f in config.factors.values())
    assert abs(total_weight - 1.0) < 1e-4, f"Weights must sum to 1.0, got {total_weight}"


def test_risk_config_validation_error_on_invalid_weights():
    """Verify RiskConfig raises ValueError if weights do not sum to 1.0."""
    invalid_factors = {
        factor: FactorConfig(name=factor, weight=0.10, description="test", parameters={})
        for factor in EXPECTED_FACTORS
    }
    # 7 * 0.10 = 0.70 != 1.00
    with pytest.raises(ValueError, match="must sum to 1.0"):
        RiskConfig(factors=invalid_factors)


def test_risk_config_validation_error_on_missing_factor():
    """Verify RiskConfig raises ValueError if any of the 7 factors is omitted."""
    incomplete_factors = {
        "major_deviation_rate": FactorConfig(name="Major", weight=1.0, description="test", parameters={})
    }
    with pytest.raises(ValueError, match="Missing required risk factor"):
        RiskConfig(factors=incomplete_factors)


# ---------------------------------------------------------------------------
# 2. Factor Normalization Unit Tests
# ---------------------------------------------------------------------------

def test_normalize_major_deviation_rate():
    """Test major deviation rate clinical threshold normalization."""
    params = {"min_rate": 0.0, "max_threshold_rate": 0.50}

    # Zero deviations = 0 score
    assert normalize_major_deviation_rate(0.0, params) == 0.0
    assert normalize_major_deviation_rate(-0.1, params) == 0.0

    # Halfway (0.25 dev/patient) = 50.0 score
    assert normalize_major_deviation_rate(0.25, params) == 50.0

    # At or above critical threshold (0.50) = 100.0 score
    assert normalize_major_deviation_rate(0.50, params) == 100.0
    assert normalize_major_deviation_rate(1.20, params) == 100.0


def test_normalize_minor_deviation_rate():
    """Test minor/administrative deviation rate normalization."""
    params = {"min_rate": 0.0, "max_threshold_rate": 1.50}

    assert normalize_minor_deviation_rate(0.0, params) == 0.0
    assert normalize_minor_deviation_rate(0.75, params) == 50.0
    assert normalize_minor_deviation_rate(1.50, params) == 100.0
    assert normalize_minor_deviation_rate(3.00, params) == 100.0


def test_normalize_deviation_trend():
    """Test deviation trajectory normalization (worsening vs. improving)."""
    params = {"recent_window_days": 60, "baseline_neutral_score": 50.0}
    as_of = date(2026, 9, 15)

    # Case 1: No deviations -> 0 risk
    score, ratio = normalize_deviation_trend([], params, as_of_date=as_of)
    assert score == 0.0
    assert ratio == 0.0

    # Case 2: All recent deviations (worsening) -> 100 risk
    recent_dates = [as_of - timedelta(days=5), as_of - timedelta(days=15)]
    score, ratio = normalize_deviation_trend(recent_dates, params, as_of_date=as_of)
    assert score == 100.0
    assert ratio == 1.0

    # Case 3: All prior deviations (improving) -> 0 risk
    prior_dates = [as_of - timedelta(days=70), as_of - timedelta(days=90)]
    score, ratio = normalize_deviation_trend(prior_dates, params, as_of_date=as_of)
    assert score == 0.0
    assert ratio == -1.0

    # Case 4: Balanced recent vs. prior -> 50 risk (neutral)
    balanced_dates = [as_of - timedelta(days=10), as_of - timedelta(days=80)]
    score, ratio = normalize_deviation_trend(balanced_dates, params, as_of_date=as_of)
    assert score == 50.0
    assert ratio == 0.0


def test_normalize_query_resolution_time():
    """Test EDC query resolution time normalization against clinical SLA benchmarks."""
    params = {"optimal_days": 5.0, "critical_days": 30.0}

    # Within standard SLA (<= 5 days) = 0 risk
    assert normalize_query_resolution_time(3.0, params) == 0.0
    assert normalize_query_resolution_time(5.0, params) == 0.0

    # Critical SLA breach (>= 30 days) = 100 risk
    assert normalize_query_resolution_time(30.0, params) == 100.0
    assert normalize_query_resolution_time(45.0, params) == 100.0

    # Midpoint: 17.5 days = 50.0 risk
    assert normalize_query_resolution_time(17.5, params) == 50.0


def test_normalize_enrollment_target():
    """Test enrollment recruitment deficit normalization."""
    params = {}

    # Target met or exceeded = 0 risk
    score, ratio = normalize_enrollment_target(40, 40, params)
    assert score == 0.0
    assert ratio == 1.0

    score, ratio = normalize_enrollment_target(50, 40, params)
    assert score == 0.0

    # Zero enrolled = 100 risk
    score, ratio = normalize_enrollment_target(0, 40, params)
    assert score == 100.0
    assert ratio == 0.0

    # 50% deficit (20 of 40) = 50 risk
    score, ratio = normalize_enrollment_target(20, 40, params)
    assert score == 50.0
    assert ratio == 0.5


def test_normalize_staff_turnover():
    """Test staff turnover rate normalization."""
    params = {"min_turnover": 0.0, "critical_turnover": 0.30}

    assert normalize_staff_turnover(0.0, params) == 0.0
    assert normalize_staff_turnover(0.15, params) == 50.0
    assert normalize_staff_turnover(0.30, params) == 100.0
    assert normalize_staff_turnover(0.45, params) == 100.0


def test_normalize_days_since_monitoring():
    """Test CRA monitoring recency normalization."""
    params = {"optimal_days": 30, "critical_days": 90}

    # Routine monitoring (<= 30 days) = 0 risk
    assert normalize_days_since_monitoring(14, params) == 0.0
    assert normalize_days_since_monitoring(30, params) == 0.0

    # Overdue (>= 90 days) = 100 risk
    assert normalize_days_since_monitoring(90, params) == 100.0
    assert normalize_days_since_monitoring(120, params) == 100.0

    # Midpoint: 60 days = 50 risk
    assert normalize_days_since_monitoring(60, params) == 50.0


# ---------------------------------------------------------------------------
# 3. Pure Engine Scoring & Mathematical Transparency Tests
# ---------------------------------------------------------------------------

def test_pure_scoring_engine_pristine_site():
    """Verify a pristine site with 0 deviations and optimal leading indicators scores 0.0."""
    indicators = {
        "enrolled_patients": 40,
        "enrollment_target": 40,
        "staff_turnover_rate": 0.0,
        "days_since_last_monitoring_visit": 14,
        "average_query_resolution_days": 3.0,
    }
    result = calculate_site_risk(deviations=[], leading_indicators=indicators)
    assert result["score"] == 0.0
    assert len(result["contributing_factors"]) == 7

    for factor in result["contributing_factors"]:
        assert factor["normalized_score"] == 0.0
        assert factor["contribution"] == 0.0


def test_pure_scoring_engine_contributing_factors_sum_and_weighting():
    """Verify each factor's contribution equals normalized_score * weight and sums correctly."""
    ref_date = date(2026, 9, 15)
    mock_deviations = [
        {"final_severity": "major", "detected_at": ref_date - timedelta(days=10)},
        {"final_severity": "major", "detected_at": ref_date - timedelta(days=20)},
        {"final_severity": "minor", "detected_at": ref_date - timedelta(days=5)},
    ]
    indicators = {
        "enrolled_patients": 10,
        "enrollment_target": 20,
        "staff_turnover_rate": 0.20,
        "days_since_last_monitoring_visit": 60,
        "average_query_resolution_days": 17.5,
    }

    result = calculate_site_risk(
        deviations=mock_deviations,
        leading_indicators=indicators,
        as_of_date=ref_date,
    )

    factors = result["contributing_factors"]
    assert len(factors) == 7

    calculated_sum = 0.0
    for factor in factors:
        # Check required schema fields
        for field in ("factor", "name", "weight", "raw_value", "normalized_score", "contribution"):
            assert field in factor, f"Missing {field} in factor breakdown"

        # Check contribution math
        expected_contribution = round(factor["normalized_score"] * factor["weight"], 2)
        assert factor["contribution"] == pytest.approx(expected_contribution, abs=0.02)
        calculated_sum += factor["contribution"]

    # Final score matches the sum of contributions
    assert result["score"] == pytest.approx(round(calculated_sum, 1), abs=0.1)


# ---------------------------------------------------------------------------
# 4. Seeded Data Integration Tests
# ---------------------------------------------------------------------------

def test_seeded_data_high_risk_and_low_risk_ordering():
    """Confirm planted high-risk site (SITE-101) scores highest and low-risk site (SITE-105) scores lowest."""
    run_seed()

    db = SessionLocal()
    try:
        as_of = date(2026, 9, 15)
        persisted_scores = compute_and_persist_site_risk_scores(db=db, as_of_date=as_of)
        assert len(persisted_scores) == 5

        scores_by_site = {s.site_id: s for s in persisted_scores}

        score_101 = scores_by_site["SITE-101"].score
        score_102 = scores_by_site["SITE-102"].score
        score_103 = scores_by_site["SITE-103"].score
        score_104 = scores_by_site["SITE-104"].score
        score_105 = scores_by_site["SITE-105"].score

        # Core requirements from prompt:
        # 1. High-risk site scores highest
        assert score_101 == max(score_101, score_102, score_103, score_104, score_105), (
            f"Planted high-risk site SITE-101 did not score highest: {score_101}"
        )
        # 2. Low-risk site scores lowest
        assert score_105 == min(score_101, score_102, score_103, score_104, score_105), (
            f"Planted low-risk site SITE-105 did not score lowest: {score_105}"
        )

        # 3. High risk site has substantial risk (> 70)
        assert score_101 > 70.0, f"Expected SITE-101 > 70.0, got {score_101}"

        # 4. Low risk site has low risk (< 30)
        assert score_105 < 30.0, f"Expected SITE-105 < 30.0, got {score_105}"

        # 5. Check contributing factors structure and sum for SITE-101
        site_101_factors = scores_by_site["SITE-101"].contributing_factors
        assert len(site_101_factors) == 7
        factor_sum = sum(f["contribution"] for f in site_101_factors)
        assert score_101 == pytest.approx(round(factor_sum, 1), abs=0.1)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. FastAPI Endpoints Integration Tests
# ---------------------------------------------------------------------------

def test_api_risk_compute_and_scores_routes():
    """Verify POST /api/risk/compute and GET /api/risk/scores endpoints work end-to-end."""
    client = TestClient(app)

    # Test POST /api/risk/compute
    response = client.post("/api/risk/compute?as_of_date=2026-09-15")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["computed_count"] == 5
    assert len(data["scores"]) == 5

    # Check first score item structure
    first_score = data["scores"][0]
    assert "score_id" in first_score
    assert "site_id" in first_score
    assert "score" in first_score
    assert "contributing_factors" in first_score
    assert len(first_score["contributing_factors"]) == 7

    # Test GET /api/risk/scores
    get_response = client.get("/api/risk/scores")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["count"] >= 5

    # Test GET /api/risk/scores?site_id=SITE-101
    site_response = client.get("/api/risk/scores?site_id=SITE-101")
    assert site_response.status_code == 200
    site_data = site_response.json()
    assert site_data["count"] >= 1
    assert site_data["scores"][0]["site_id"] == "SITE-101"
