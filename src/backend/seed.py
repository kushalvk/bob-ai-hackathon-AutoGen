"""Synthetic Seed Data Generator for ClinGuard AI.

Generates reproducible, synthetic clinical trial dataset with realistic site risk profiles,
patient visit histories, and planted protocol deviations. Exports a baseline JSON fixture
`src/backend/fixtures/expected_deviations.json` for deterministic test assertions.
"""

import json
import os
import random
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from src.backend.database import engine, SessionLocal, Base
from src.backend.models import (
    Protocol,
    Site,
    Patient,
    VisitRecord,
    Deviation,
    SiteRiskScore,
    CAPAReport,
)
from src.backend.risk.engine import calculate_site_risk

# Set deterministic random seed
SEED_VALUE = 42
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
EXPECTED_DEVIATIONS_PATH = os.path.join(FIXTURES_DIR, "expected_deviations.json")


def create_protocol(db: Session) -> Protocol:
    """Create and return the primary synthetic clinical trial protocol.

    Args:
        db (Session): Active database session.

    Returns:
        Protocol: Created protocol model instance.
    """
    protocol = Protocol(
        protocol_id="PROTO-001",
        title="Phase II Double-Blind Study of ClinGuard-A/B in Moderate Hypercholesterolemia",
        version="1.0",
        visit_schedule=[
            {"visit_name": "Screening", "day_offset": 0, "window_days": 3},
            {"visit_name": "Baseline", "day_offset": 7, "window_days": 3},
            {"visit_name": "Week 2", "day_offset": 21, "window_days": 3},
            {"visit_name": "Week 4", "day_offset": 35, "window_days": 5},
            {"visit_name": "Week 8", "day_offset": 63, "window_days": 5},
            {"visit_name": "Completion", "day_offset": 91, "window_days": 7},
        ],
        dosing_schedule=[
            {"visit_name": "Screening", "drug": None, "dose": 0.0, "unit": "mg"},
            {"visit_name": "Baseline", "drug": "ClinGuard-A", "dose": 50.0, "unit": "mg"},
            {"visit_name": "Week 2", "drug": "ClinGuard-A", "dose": 50.0, "unit": "mg"},
            {"visit_name": "Week 4", "drug": "ClinGuard-B", "dose": 10.0, "unit": "mg"},
            {"visit_name": "Week 8", "drug": "ClinGuard-B", "dose": 10.0, "unit": "mg"},
            {"visit_name": "Completion", "drug": "ClinGuard-B", "dose": 10.0, "unit": "mg"},
        ],
        prohibited_medications=[
            "Ketoconazole",
            "Clarithromycin",
            "St. John's Wort",
            "Rifampin",
        ],
        eligibility_criteria=[
            "Age between 18 and 75 years at screening",
            "ALT and AST <= 2.5x Upper Limit of Normal (ULN)",
            "No prior history of severe hepatic impairment or acute liver disease",
            "Written informed consent signed prior to any study procedure",
        ],
    )
    db.add(protocol)
    db.flush()
    return protocol


def create_sites(db: Session) -> List[Site]:
    """Create 5 trial sites with varying operational risk profiles.

    Risk profiles:
    - SITE-101: High risk (high staff turnover 35%, frequent deviations)
    - SITE-102, 103, 104: Mixed risk (moderate turnover 8-15%)
    - SITE-105: Low risk (low turnover 2%, minimal deviations)

    Args:
        db (Session): Active database session.

    Returns:
        List[Site]: Created site model instances.
    """
    sites_data = [
        {
            "site_id": "SITE-101",
            "name": "Metro General Research Center",
            "country": "USA",
            "enrollment_target": 40,
            "staff_turnover_rate": 0.35,
            "last_monitoring_visit_date": date(2026, 6, 15),
            "average_query_resolution_days": 24.5,
        },
        {
            "site_id": "SITE-102",
            "name": "St. Jude Clinical Institute",
            "country": "UK",
            "enrollment_target": 35,
            "staff_turnover_rate": 0.15,
            "last_monitoring_visit_date": date(2026, 7, 20),
            "average_query_resolution_days": 14.0,
        },
        {
            "site_id": "SITE-103",
            "name": "Heidelberg University Hospital",
            "country": "Germany",
            "enrollment_target": 30,
            "staff_turnover_rate": 0.12,
            "last_monitoring_visit_date": date(2026, 8, 10),
            "average_query_resolution_days": 11.5,
        },
        {
            "site_id": "SITE-104",
            "name": "Tokyo Medical Research Hub",
            "country": "Japan",
            "enrollment_target": 35,
            "staff_turnover_rate": 0.08,
            "last_monitoring_visit_date": date(2026, 8, 25),
            "average_query_resolution_days": 8.0,
        },
        {
            "site_id": "SITE-105",
            "name": "Nordic Health Trial Site",
            "country": "Sweden",
            "enrollment_target": 25,
            "staff_turnover_rate": 0.02,
            "last_monitoring_visit_date": date(2026, 9, 1),
            "average_query_resolution_days": 3.5,
        },
    ]

    sites = []
    for data in sites_data:
        site = Site(**data)
        db.add(site)
        sites.append(site)
    db.flush()
    return sites


def create_patients_and_visit_records(
    db: Session, protocol: Protocol, sites: List[Site]
) -> tuple[List[Patient], List[VisitRecord], List[Dict[str, Any]], List[Deviation]]:
    """Generate 35 patients and ~175 visit records with planted protocol deviations.

    Plant explicit deviations across all 5 categories:
    1. missed_visit (visit skipped or out of window)
    2. wrong_dose (dose given differs from protocol schedule)
    3. banned_comed (prohibited concomitant medication reported)
    4. eligibility_breach (enrollment despite lab/criterion failure)
    5. documentation (missing mandatory signatures or dose logs)

    Args:
        db (Session): Active database session.
        protocol (Protocol): Trial protocol instance.
        sites (List[Site]): List of site instances.

    Returns:
        tuple: Created (patients, visit_records, expected_deviations_fixture, deviation_models)
    """
    base_date = date(2026, 1, 10)
    patients = []
    visit_records = []
    expected_deviations = []
    deviation_models = []

    # Map site risk level to deviation propensity
    site_risk_map = {
        "SITE-101": "high",    # High risk -> ~50% of deviations
        "SITE-102": "mixed",   # Mixed
        "SITE-103": "mixed",   # Mixed
        "SITE-104": "mixed",   # Mixed
        "SITE-105": "low",     # Low risk -> minimal/no deviations
    }

    patient_counter = 1
    record_counter = 1
    dev_counter = 1

    visit_schedule = protocol.visit_schedule
    dosing_map = {item["visit_name"]: item for item in protocol.dosing_schedule}

    safe_comed_pool = ["Paracetamol 500mg", "Ibuprofen 200mg", "Multivitamin Daily", "Omeprazole 20mg", "Loratadine 10mg"]
    banned_comed_pool = ["Ketoconazole", "Clarithromycin", "Rifampin"]

    for site in sites:
        risk_level = site_risk_map[site.site_id]
        num_patients = 7  # 7 patients per site = 35 total

        for p_idx in range(num_patients):
            patient_id = f"PAT-{site.site_id.split('-')[1]}-{p_idx + 1:03d}"
            # Stagger enrollment date
            enrollment_offset = random.randint(0, 30)
            patient_enrollment = base_date + timedelta(days=enrollment_offset)

            patient = Patient(
                patient_id=patient_id,
                site_id=site.site_id,
                enrollment_date=patient_enrollment,
            )
            db.add(patient)
            patients.append(patient)

            # Generate visit records for all 5 visits for this patient
            for v_idx, visit_meta in enumerate(visit_schedule):
                v_name = visit_meta["visit_name"]
                day_offset = visit_meta["day_offset"]
                window_days = visit_meta["window_days"]
                dosing_spec = dosing_map[v_name]

                scheduled_dt = patient_enrollment + timedelta(days=day_offset)
                rec_id = f"REC-{record_counter:04d}"
                record_counter += 1

                # Determine if we plant a deviation on this record
                plant_dev_type = None
                
                # Higher probability of deviation for high risk site, lower for mixed, virtually none for low
                if risk_level == "high":
                    rand_val = random.random()
                    if rand_val < 0.28:
                        plant_dev_type = random.choice(["missed_visit", "wrong_dose", "banned_comed", "documentation", "eligibility_breach"])
                elif risk_level == "mixed":
                    rand_val = random.random()
                    if rand_val < 0.10:
                        plant_dev_type = random.choice(["missed_visit", "wrong_dose", "banned_comed", "documentation"])
                elif risk_level == "low":
                    rand_val = random.random()
                    if rand_val < 0.02 and v_name == "Week 4":
                        plant_dev_type = "documentation"

                # Ensure we hit all 5 deviation types deterministically at specific records if random missed any
                # Special fixed planted deviations to guarantee coverage
                if patient_id == "PAT-101-001" and v_name == "Screening":
                    plant_dev_type = "eligibility_breach"
                elif patient_id == "PAT-101-002" and v_name == "Week 2":
                    plant_dev_type = "wrong_dose"
                elif patient_id == "PAT-101-003" and v_name == "Week 4":
                    plant_dev_type = "banned_comed"
                elif patient_id == "PAT-101-004" and v_name == "Week 8":
                    plant_dev_type = "missed_visit"
                elif patient_id == "PAT-102-001" and v_name == "Baseline":
                    plant_dev_type = "documentation"

                actual_dt = scheduled_dt + timedelta(days=random.randint(-1, 1))
                dose_given = dosing_spec["dose"]
                drug = dosing_spec["drug"]
                comeds = random.sample(safe_comed_pool, k=random.randint(0, 2))
                notes = f"Visit {v_name} completed per protocol."

                dev_model = None

                if plant_dev_type == "missed_visit":
                    actual_dt = scheduled_dt + timedelta(days=window_days + random.randint(12, 20))
                    days_late = (actual_dt - scheduled_dt).days
                    notes = f"Patient arrived {days_late} days late for {v_name} visit, outside allowable +-{window_days} day window."
                    dev_id = f"DEV-{dev_counter:04d}"
                    dev_counter += 1
                    severity = "major"
                    rationale = f"Visit conducted {days_late} days past window. Exceeds protocol specified tolerance of +-{window_days} days."
                    min_allowed = scheduled_dt - timedelta(days=window_days)
                    max_allowed = scheduled_dt + timedelta(days=window_days)
                    evidence = {
                        "field": "actual_date",
                        "expected": {
                            "scheduled_date": scheduled_dt.isoformat(),
                            "window_days": window_days,
                            "allowed_range": [min_allowed.isoformat(), max_allowed.isoformat()],
                        },
                        "actual": actual_dt.isoformat(),
                        "delta": {
                            "days_offset_from_scheduled": days_late,
                            "days_outside_window": days_late - window_days,
                        },
                    }
                    
                    dev_model = Deviation(
                        deviation_id=dev_id,
                        record_id=rec_id,
                        site_id=site.site_id,
                        type="missed_visit",
                        severity=severity,
                        default_severity=severity,
                        final_severity=severity,
                        severity_source="deterministic",
                        severity_rationale=rationale,
                        evidence=evidence,
                        detected_at=datetime.combine(actual_dt, datetime.min.time()) + timedelta(hours=10),
                    )

                elif plant_dev_type == "wrong_dose":
                    # Administer double or wrong dose
                    dose_given = dosing_spec["dose"] * 2.0 if dosing_spec["dose"] > 0 else 100.0
                    notes = f"Subject administered incorrect dose of {dose_given} mg instead of protocol target {dosing_spec['dose']} mg."
                    dev_id = f"DEV-{dev_counter:04d}"
                    dev_counter += 1
                    severity = "major"
                    rationale = f"Administered dose ({dose_given} mg) deviates from protocol specification ({dosing_spec['dose']} mg)."
                    diff = abs(dose_given - dosing_spec["dose"])
                    pct_dev = round((diff / (dosing_spec["dose"] if dosing_spec["dose"] > 0 else 1.0)) * 100.0, 1)
                    evidence = {
                        "field": "dose_given",
                        "expected": {"drug": dosing_spec["drug"], "dose": dosing_spec["dose"], "unit": "mg"},
                        "actual": {"drug": drug, "dose": dose_given, "unit": "mg"},
                        "delta": {
                            "absolute_difference": diff,
                            "percentage_deviation": pct_dev,
                            "allowed_tolerance_pct": 5.0,
                        },
                    }
                    
                    dev_model = Deviation(
                        deviation_id=dev_id,
                        record_id=rec_id,
                        site_id=site.site_id,
                        type="wrong_dose",
                        severity=severity,
                        default_severity=severity,
                        final_severity=severity,
                        severity_source="deterministic",
                        severity_rationale=rationale,
                        evidence=evidence,
                        detected_at=datetime.combine(actual_dt, datetime.min.time()) + timedelta(hours=11),
                    )

                elif plant_dev_type == "banned_comed":
                    banned_drug = random.choice(banned_comed_pool)
                    comeds.append(banned_drug)
                    notes = f"Concomitant medication log lists {banned_drug}, which is prohibited by protocol section 5.2."
                    dev_id = f"DEV-{dev_counter:04d}"
                    dev_counter += 1
                    severity = "major"
                    rationale = f"Concomitant administration of prohibited CYP3A4 inhibitor ({banned_drug})."
                    evidence = {
                        "field": "concomitant_meds",
                        "expected": {"prohibited_medications": protocol.prohibited_medications},
                        "actual": banned_drug,
                        "delta": f"Reported concomitant drug '{banned_drug}' matches prohibited drug list",
                    }

                    dev_model = Deviation(
                        deviation_id=dev_id,
                        record_id=rec_id,
                        site_id=site.site_id,
                        type="banned_comed",
                        severity=severity,
                        default_severity=severity,
                        final_severity=severity,
                        severity_source="deterministic",
                        severity_rationale=rationale,
                        evidence=evidence,
                        detected_at=datetime.combine(actual_dt, datetime.min.time()) + timedelta(hours=14),
                    )

                elif plant_dev_type == "eligibility_breach":
                    notes = "Baseline screening lab revealed ALT 3.8x ULN, violating Inclusion/Exclusion criterion #2 (ALT <= 2.5x ULN). Patient enrolled anyway."
                    dev_id = f"DEV-{dev_counter:04d}"
                    dev_counter += 1
                    severity = "major"
                    rationale = "Subject enrolled despite exceeding AST/ALT upper limit threshold established in eligibility criteria."
                    evidence = {
                        "field": "eligibility_criteria",
                        "expected": {
                            "criterion": "ALT and AST <= 2.5x Upper Limit of Normal (ULN)",
                            "criteria_list": protocol.eligibility_criteria,
                        },
                        "actual": notes,
                        "delta": "Matched eligibility violation keyword in clinical notes",
                    }

                    dev_model = Deviation(
                        deviation_id=dev_id,
                        record_id=rec_id,
                        site_id=site.site_id,
                        type="eligibility_breach",
                        severity=severity,
                        default_severity=severity,
                        final_severity=severity,
                        severity_source="deterministic",
                        severity_rationale=rationale,
                        evidence=evidence,
                        detected_at=datetime.combine(actual_dt, datetime.min.time()) + timedelta(hours=9),
                    )

                elif plant_dev_type == "documentation":
                    notes = "Dose administration record missing Principal Investigator signature and verification stamp."
                    dev_id = f"DEV-{dev_counter:04d}"
                    dev_counter += 1
                    severity = "minor"
                    rationale = "Administrative documentation gap: missing required investigator signature on source log."
                    evidence = {
                        "field": "notes",
                        "expected": "Complete clinical visit notes with Principal Investigator signature verification.",
                        "actual": notes,
                        "delta": "Documentation gap identified by keyword: missing signature",
                    }

                    dev_model = Deviation(
                        deviation_id=dev_id,
                        record_id=rec_id,
                        site_id=site.site_id,
                        type="documentation",
                        severity=severity,
                        default_severity=severity,
                        final_severity=severity,
                        severity_source="deterministic",
                        severity_rationale=rationale,
                        evidence=evidence,
                        detected_at=datetime.combine(actual_dt, datetime.min.time()) + timedelta(hours=16),
                    )

                rec = VisitRecord(
                    record_id=rec_id,
                    patient_id=patient_id,
                    visit_name=v_name,
                    scheduled_date=scheduled_dt,
                    actual_date=actual_dt,
                    dose_given=dose_given,
                    drug=drug,
                    concomitant_meds=comeds,
                    notes=notes,
                )
                db.add(rec)
                visit_records.append(rec)

                if dev_model:
                    db.add(dev_model)
                    deviation_models.append(dev_model)
                    expected_deviations.append({
                        "deviation_id": dev_model.deviation_id,
                        "record_id": rec_id,
                        "patient_id": patient_id,
                        "site_id": site.site_id,
                        "visit_name": v_name,
                        "type": dev_model.type,
                        "severity": dev_model.severity,
                        "severity_rationale": dev_model.severity_rationale,
                        "evidence": dev_model.evidence,
                        "detected_at": dev_model.detected_at.isoformat(),
                    })

    db.flush()
    return patients, visit_records, expected_deviations, deviation_models


def create_site_risk_scores_and_capas(
    db: Session,
    sites: List[Site],
    deviations: List[Deviation],
    patients: List[Patient] = None,
) -> tuple[List[SiteRiskScore], List[CAPAReport]]:
    """Compute and persist deterministic site risk scores (0-100) and CAPA reports.

    Uses the 7-factor deterministic site risk scoring formula with full factor breakdown.

    Args:
        db (Session): Active database session.
        sites (List[Site]): Site instances.
        deviations (List[Deviation]): Planted deviations.
        patients (List[Patient], optional): Patient instances.

    Returns:
        tuple: (site_risk_scores, capa_reports)
    """
    scores = []
    capas = []
    as_of = datetime(2026, 9, 15, 12, 0, 0)
    as_of_dt = as_of.date()

    if patients is None:
        patients = db.query(Patient).all()

    for site in sites:
        site_devs = [d for d in deviations if d.site_id == site.site_id]
        site_patients = [p for p in patients if p.site_id == site.site_id]
        major_devs = len([d for d in site_devs if (getattr(d, 'final_severity', None) or getattr(d, 'severity', None)) == "major"])

        indicators = {
            "enrolled_patients": len(site_patients),
            "enrollment_target": site.enrollment_target,
            "staff_turnover_rate": site.staff_turnover_rate,
            "last_monitoring_visit_date": site.last_monitoring_visit_date,
            "average_query_resolution_days": site.average_query_resolution_days,
        }

        risk_result = calculate_site_risk(
            deviations=site_devs,
            leading_indicators=indicators,
            as_of_date=as_of_dt,
        )

        total_score = risk_result["score"]
        factors = risk_result["contributing_factors"]

        score_model = SiteRiskScore(
            score_id=f"RISK-{site.site_id.split('-')[1]}-20260915",
            site_id=site.site_id,
            score=total_score,
            computed_at=as_of,
            contributing_factors=factors,
        )
        db.add(score_model)
        scores.append(score_model)

        # Generate CAPA for high-risk site or sites with major deviations
        if major_devs > 0:
            dev_ids = [d.deviation_id for d in site_devs if (getattr(d, 'final_severity', None) or getattr(d, 'severity', None)) == "major"]
            capa = CAPAReport(
                capa_id=f"CAPA-{site.site_id.split('-')[1]}-001",
                deviation_ids=dev_ids,
                root_cause=f"High staff turnover ({site.staff_turnover_rate * 100:.0f}%) led to inadequate coordinator onboarding and protocol adherence.",
                corrective_action="Re-train all site clinical research coordinators on protocol eligibility, dosing schedules, and prohibited comed logs.",
                preventive_action="Implement mandatory pre-screening checklist and double-check signoff for dose administration.",
                owner="Quality Assurance Manager (Dr. E. Vance)",
                due_date=date(2026, 10, 15),
                status="open" if total_score > 60 else "in_progress",
            )
            db.add(capa)
            capas.append(capa)

    db.flush()
    return scores, capas


def run_seed() -> None:
    """Execute main database seeding process."""
    random.seed(SEED_VALUE)
    
    # Re-create tables cleanly
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Clear existing tables in reverse dependency order
        db.query(CAPAReport).delete()
        db.query(SiteRiskScore).delete()
        db.query(Deviation).delete()
        db.query(VisitRecord).delete()
        db.query(Patient).delete()
        db.query(Site).delete()
        db.query(Protocol).delete()
        db.commit()

        print("[SEED] Generating Protocol...")
        protocol = create_protocol(db)

        print("[SEED] Generating Sites...")
        sites = create_sites(db)

        print("[SEED] Generating Patients, Visit Records, and Planted Deviations...")
        patients, visit_records, expected_deviations, deviations = create_patients_and_visit_records(
            db, protocol, sites
        )

        print("[SEED] Generating Site Risk Scores and CAPA Reports...")
        scores, capas = create_site_risk_scores_and_capas(db, sites, deviations)

        db.commit()

        # Save expected_deviations.json fixture
        os.makedirs(FIXTURES_DIR, exist_ok=True)
        with open(EXPECTED_DEVIATIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(expected_deviations, f, indent=2)

        print("\n--- SEED SUMMARY ---")
        print(f"Protocol created: {protocol.protocol_id}")
        print(f"Sites created: {len(sites)}")
        print(f"Patients created: {len(patients)}")
        print(f"Visit Records created: {len(visit_records)}")
        print(f"Planted Deviations created: {len(deviations)}")
        print(f"Site Risk Scores calculated: {len(scores)}")
        print(f"CAPA Reports generated: {len(capas)}")
        print(f"Expected deviations baseline exported to: {EXPECTED_DEVIATIONS_PATH}")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] Failed to seed database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
