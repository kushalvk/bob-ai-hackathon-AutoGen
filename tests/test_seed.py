"""Integration tests for database seed script and planted deviations baseline."""

import json
import os
from src.backend.database import SessionLocal
from src.backend.models import Protocol, Site, Patient, VisitRecord, Deviation, SiteRiskScore, CAPAReport


def test_seed_database_entities():
    """Verify seeded database contains protocol, sites, patients, and visit records."""
    db = SessionLocal()
    try:
        protocols = db.query(Protocol).all()
        assert len(protocols) >= 1
        assert protocols[0].protocol_id == "PROTO-001"

        sites = db.query(Site).all()
        assert len(sites) == 5

        patients = db.query(Patient).all()
        assert len(patients) == 35

        records = db.query(VisitRecord).all()
        assert len(records) >= 150

        scores = db.query(SiteRiskScore).all()
        assert len(scores) == 5

        capas = db.query(CAPAReport).all()
        assert len(capas) >= 1
    finally:
        db.close()


def test_expected_deviations_fixture():
    """Verify expected_deviations.json fixture exists and covers all 5 deviation types."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "backend", "fixtures", "expected_deviations.json"
    )
    assert os.path.exists(fixture_path), "expected_deviations.json fixture file missing"

    with open(fixture_path, "r", encoding="utf-8") as f:
        deviations_fixture = json.load(f)

    assert len(deviations_fixture) > 0

    types_found = {d["type"] for d in deviations_fixture}
    expected_types = {"missed_visit", "wrong_dose", "banned_comed", "eligibility_breach", "documentation"}

    assert expected_types.issubset(types_found), f"Missing deviation types: {expected_types - types_found}"
