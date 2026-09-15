"""Comprehensive unit and integration tests for Deviation Detection Engine."""

import json
import os
from datetime import date, timedelta
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.database import SessionLocal
from src.backend.models import Protocol, VisitRecord
from src.backend.detection.synonyms import is_prohibited_comedication, normalize_drug_name
from src.backend.detection.engine import (
    check_missed_or_out_of_window_visit,
    check_wrong_dose,
    check_banned_comedication,
    check_eligibility_breach,
    check_documentation_gap,
    run_detection_pipeline,
)

client = TestClient(app)


# --- 1. Synonyms & Drug Matching Unit Tests ---

def test_normalize_drug_name():
    """Test drug string normalization."""
    assert normalize_drug_name("Ketoconazole 200mg") == "ketoconazole 200mg"
    assert normalize_drug_name("Biaxin (Clarithromycin)!") == "biaxin clarithromycin"
    assert normalize_drug_name("") == ""


def test_synonym_banned_comedication_matching():
    """Test synonym and fuzzy matching for prohibited drugs."""
    prohibited = ["Ketoconazole", "Clarithromycin", "St. John's Wort", "Rifampin"]

    # Exact match
    is_banned, matched = is_prohibited_comedication("Ketoconazole", prohibited)
    assert is_banned is True
    assert matched == "Ketoconazole"

    # Brand synonym match
    is_banned, matched = is_prohibited_comedication("Nizoral 200mg", prohibited)
    assert is_banned is True
    assert matched == "Ketoconazole"

    # Brand synonym match 2
    is_banned, matched = is_prohibited_comedication("Biaxin XL", prohibited)
    assert is_banned is True
    assert matched == "Clarithromycin"

    # Safe drug
    is_banned, matched = is_prohibited_comedication("Paracetamol 500mg", prohibited)
    assert is_banned is False
    assert matched is None


# --- 2. Isolated Rule Evaluator Unit Tests ---

def test_check_missed_or_out_of_window_visit():
    """Test Rule 1 evaluator with in-window, out-of-window, and missed visits."""
    sched = date(2026, 3, 1)
    spec = {"visit_name": "Week 2", "day_offset": 21, "window_days": 3}

    # In window (1 day late) -> No deviation
    rec_clean = {"record_id": "R1", "patient_id": "P1", "scheduled_date": sched, "actual_date": sched + timedelta(days=1)}
    assert check_missed_or_out_of_window_visit(rec_clean, spec) is None

    # Out of window (10 days late) -> Flagged
    rec_late = {"record_id": "R2", "patient_id": "P1", "scheduled_date": sched, "actual_date": sched + timedelta(days=10)}
    dev = check_missed_or_out_of_window_visit(rec_late, spec)
    assert dev is not None
    assert dev["type"] == "missed_visit"
    assert dev["evidence"]["field"] == "actual_date"
    assert dev["evidence"]["delta"]["days_outside_window"] == 7

    # Missed visit (None actual_date) -> Flagged
    rec_missed = {"record_id": "R3", "patient_id": "P1", "scheduled_date": sched, "actual_date": None}
    dev_m = check_missed_or_out_of_window_visit(rec_missed, spec)
    assert dev_m is not None
    assert dev_m["type"] == "missed_visit"
    assert dev_m["evidence"]["actual"] is None


def test_check_wrong_dose():
    """Test Rule 2 evaluator with tolerance threshold and drug mismatch."""
    dosing_spec = {"visit_name": "Week 4", "drug": "ClinGuard-B", "dose": 10.0, "unit": "mg"}

    # Exact dose -> Clean
    rec_exact = {"record_id": "R1", "patient_id": "P1", "drug": "ClinGuard-B", "dose_given": 10.0}
    assert check_wrong_dose(rec_exact, dosing_spec, tolerance=0.05) is None

    # Within 5% tolerance (10.4mg = 4% dev) -> Clean
    rec_tol = {"record_id": "R2", "patient_id": "P1", "drug": "ClinGuard-B", "dose_given": 10.4}
    assert check_wrong_dose(rec_tol, dosing_spec, tolerance=0.05) is None

    # Exceeding 5% tolerance (20.0mg = 100% dev) -> Flagged
    rec_wrong = {"record_id": "R3", "patient_id": "P1", "drug": "ClinGuard-B", "dose_given": 20.0}
    dev = check_wrong_dose(rec_wrong, dosing_spec, tolerance=0.05)
    assert dev is not None
    assert dev["type"] == "wrong_dose"
    assert dev["evidence"]["field"] == "dose_given"
    assert dev["evidence"]["delta"]["percentage_deviation"] == 100.0

    # Drug mismatch -> Flagged
    rec_mismatch = {"record_id": "R4", "patient_id": "P1", "drug": "ClinGuard-A", "dose_given": 10.0}
    dev_m = check_wrong_dose(rec_mismatch, dosing_spec, tolerance=0.05)
    assert dev_m is not None
    assert dev_m["evidence"]["delta"] == "Drug name mismatch"


def test_check_banned_comedication():
    """Test Rule 3 evaluator with safe and prohibited concomitant meds."""
    prohibited = ["Ketoconazole", "Rifampin"]

    # Safe meds -> Clean
    rec_safe = {"record_id": "R1", "patient_id": "P1", "concomitant_meds": ["Paracetamol 500mg", "Ibuprofen"]}
    assert check_banned_comedication(rec_safe, prohibited) is None

    # Prohibited med -> Flagged
    rec_banned = {"record_id": "R2", "patient_id": "P1", "concomitant_meds": ["Paracetamol", "Nizoral 200mg"]}
    dev = check_banned_comedication(rec_banned, prohibited)
    assert dev is not None
    assert dev["type"] == "banned_comed"
    assert dev["evidence"]["actual"] == "Nizoral 200mg"


def test_check_eligibility_breach():
    """Test Rule 4 evaluator for eligibility breaches."""
    # Clean notes -> Clean
    rec_clean = {"record_id": "R1", "patient_id": "P1", "notes": "Visit completed without issue."}
    assert check_eligibility_breach(rec_clean) is None

    # Eligibility breach notes -> Flagged
    rec_breach = {"record_id": "R2", "patient_id": "P1", "notes": "Screening lab ALT 3.8x ULN, violating Inclusion/Exclusion criterion #2."}
    dev = check_eligibility_breach(rec_breach)
    assert dev is not None
    assert dev["type"] == "eligibility_breach"


def test_check_documentation_gap():
    """Test Rule 5 evaluator for documentation gaps."""
    # Clean notes -> Clean
    rec_clean = {"record_id": "R1", "patient_id": "P1", "notes": "Dose administered by CRC. Signed by PI."}
    assert check_documentation_gap(rec_clean) is None

    # Missing PI signature -> Flagged
    rec_gap = {"record_id": "R2", "patient_id": "P1", "notes": "Dose record missing Principal Investigator signature."}
    dev = check_documentation_gap(rec_gap)
    assert dev is not None
    assert dev["type"] == "documentation"
    assert dev["severity"] == "minor"


# --- 3. End-to-End Integration & Fixture Assertions ---

def test_detection_engine_against_seeded_data():
    """Assert 100% recall against expected_deviations.json baseline with zero false positives on clean records."""
    db = SessionLocal()
    try:
        protocol = db.query(Protocol).filter(Protocol.protocol_id == "PROTO-001").first()
        records = db.query(VisitRecord).all()

        # Execute pure pipeline
        candidate_devs = run_detection_pipeline(protocol, records)

        # Load expected deviations fixture
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "backend", "fixtures", "expected_deviations.json"
        )
        with open(fixture_path, "r", encoding="utf-8") as f:
            expected_fixture = json.load(f)

        expected_by_record = {item["record_id"]: item for item in expected_fixture}
        detected_by_record = {item["record_id"]: item for item in candidate_devs}

        # 1. Assert 100% recall (every planted deviation record is detected)
        for rec_id, expected_dev in expected_by_record.items():
            assert rec_id in detected_by_record, f"Planted deviation record {rec_id} was missed by detection engine!"
            detected_dev = detected_by_record[rec_id]
            assert detected_dev["type"] == expected_dev["type"], (
                f"Record {rec_id}: expected type '{expected_dev['type']}', got '{detected_dev['type']}'"
            )
            # Verify evidence payload structure
            assert "evidence" in detected_dev
            assert "field" in detected_dev["evidence"]
            assert "expected" in detected_dev["evidence"]
            assert "actual" in detected_dev["evidence"]

        # 2. Assert 0 false positives (no unplanted clean records were flagged)
        assert len(candidate_devs) == len(expected_fixture), (
            f"Expected exactly {len(expected_fixture)} deviations, but engine detected {len(candidate_devs)} (false positives present)"
        )

    finally:
        db.close()


# --- 4. FastAPI Endpoint Tests ---

def test_post_detect_run_endpoint():
    """Test POST /api/detect/run endpoint."""
    response = client.post("/api/detect/run?protocol_id=PROTO-001")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_deviations_detected"] == 24
    assert "deviations_by_type" in data
    assert data["deviations_by_type"]["missed_visit"] > 0
    assert data["deviations_by_type"]["wrong_dose"] > 0


def test_get_detect_results_endpoint():
    """Test GET /api/detect/results endpoint."""
    response = client.get("/api/detect/results")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 24
    assert len(data["deviations"]) == 24
    
    first_dev = data["deviations"][0]
    assert "deviation_id" in first_dev
    assert "evidence" in first_dev
    assert "field" in first_dev["evidence"]
