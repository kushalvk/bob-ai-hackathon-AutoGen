"""Persistence service wrapper for Deviation Detection Engine."""

from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.backend.models import Protocol, Patient, VisitRecord, Deviation, Site
from src.backend.detection.engine import run_detection_pipeline


def execute_detection_run(db: Session, protocol_id: str = "PROTO-001") -> List[Deviation]:
    """Load protocol and visit records from DB, run detection pipeline, and persist deviations.

    Args:
        db (Session): Active database session.
        protocol_id (str): Target protocol ID to analyze.

    Returns:
        List[Deviation]: List of persisted Deviation SQLAlchemy model instances.
    """
    protocol = db.query(Protocol).filter(Protocol.protocol_id == protocol_id).first()
    if not protocol:
        raise ValueError(f"Protocol '{protocol_id}' not found in database.")

    # Load all patients and build patient_id -> Patient map
    patients = db.query(Patient).all()
    patients_map = {p.patient_id: p for p in patients}

    # Load all visit records with patient and site relationship
    records = db.query(VisitRecord).all()

    # Map record_id -> site_id
    patient_site_map = {p.patient_id: p.site_id for p in patients}

    # Run pure deterministic detection pipeline
    candidate_devs = run_detection_pipeline(
        protocol=protocol,
        visit_records=records,
        patients_map=patients_map,
    )

    # Clear existing non-seeded or sync existing deviations
    db.query(Deviation).delete()
    db.flush()

    persisted_deviations = []
    now = datetime.now()

    for idx, candidate in enumerate(candidate_devs, start=1):
        rec_id = candidate["record_id"]
        p_id = candidate["patient_id"]
        site_id = patient_site_map.get(p_id, "SITE-101")
        dev_id = f"DEV-{idx:04d}"

        dev_model = Deviation(
            deviation_id=dev_id,
            record_id=rec_id,
            site_id=site_id,
            type=candidate["type"],
            severity=candidate["severity"],
            severity_rationale=candidate["severity_rationale"],
            evidence=candidate["evidence"],
            detected_at=now,
        )
        db.add(dev_model)
        persisted_deviations.append(dev_model)

    db.commit()
    return persisted_deviations
