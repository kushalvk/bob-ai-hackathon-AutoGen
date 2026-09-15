"""Persistence service wrapper for Deviation Detection Engine.

Orchestrates detection pipeline execution, hybrid severity classification,
and persistence of Deviation rows with full audit trail fields.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.backend.models import Protocol, Patient, VisitRecord, Deviation, Site
from src.backend.detection.engine import run_detection_pipeline
from src.backend.detection.severity_classifier import classify_severity
from src.backend.llm_client import BaseLLMClient, get_llm_client


def execute_detection_run(
    db: Session,
    protocol_id: str = "PROTO-001",
    llm_client: Optional[BaseLLMClient] = None,
) -> List[Deviation]:
    """Load protocol and visit records, run detection pipeline, classify severity, and persist.

    Orchestration flow:
    1. Load protocol, patients, and visit records from the database.
    2. Run the deterministic detection pipeline (5 rule evaluators).
    3. For each candidate deviation, run the hybrid severity classifier
       (deterministic rules table + optional LLM review).
    4. Persist Deviation rows with dual-severity fields for audit trail.

    Args:
        db (Session): Active database session.
        protocol_id (str): Target protocol ID to analyze.
        llm_client (Optional[BaseLLMClient]): LLM client for ambiguous case review.
            If None, attempts to create one from environment config via get_llm_client().

    Returns:
        List[Deviation]: List of persisted Deviation SQLAlchemy model instances.

    Raises:
        ValueError: If the specified protocol is not found in the database.
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

    # Resolve LLM client: use injected client, or try environment config
    if llm_client is None:
        llm_client = get_llm_client()

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

        # --- Hybrid Severity Classification ---
        classification = classify_severity(candidate, llm_client=llm_client)

        dev_model = Deviation(
            deviation_id=dev_id,
            record_id=rec_id,
            site_id=site_id,
            type=candidate["type"],
            # Backward-compatible severity = final_severity
            severity=classification["final_severity"],
            default_severity=classification["default_severity"],
            final_severity=classification["final_severity"],
            severity_rationale=classification["severity_rationale"],
            severity_source=classification["severity_source"],
            evidence=candidate["evidence"],
            detected_at=now,
        )
        db.add(dev_model)
        persisted_deviations.append(dev_model)

    db.commit()
    return persisted_deviations

