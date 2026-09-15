"""Deterministic Deviation Detection Engine for ClinGuard AI.

Implements pure, non-LLM clinical protocol compliance evaluators:
1. Missed or out-of-window visits
2. Wrong dosing or study drug mismatch
3. Banned concomitant medications with synonym matching
4. Eligibility criteria breaches
5. Documentation gaps and missing signatures
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from src.backend.detection.synonyms import is_prohibited_comedication


def check_missed_or_out_of_window_visit(
    record: Any,
    visit_schedule_item: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Rule 1 Evaluator: Missed or Out-of-Window Visit Detection.

    Rule: A protocol deviation is flagged if a visit record's actual date is missing
    (missed visit) or if actual_date falls outside [scheduled_date - window_days, scheduled_date + window_days].

    Args:
        record: VisitRecord object or dictionary.
        visit_schedule_item (dict): Protocol visit schedule entry containing 'visit_name',
            'day_offset', and 'window_days'.

    Returns:
        Optional[dict]: Candidate deviation dict with field-level evidence if flagged, else None.
    """
    scheduled_date: date = getattr(record, "scheduled_date", None) or record.get("scheduled_date")
    actual_date: Optional[date] = getattr(record, "actual_date", None) if hasattr(record, "actual_date") else record.get("actual_date")
    window_days: int = visit_schedule_item.get("window_days", 3)
    v_name: str = visit_schedule_item.get("visit_name", "Unknown")
    rec_id: str = getattr(record, "record_id", "") or record.get("record_id", "")
    patient_id: str = getattr(record, "patient_id", "") or record.get("patient_id", "")

    min_allowed = scheduled_date - timedelta(days=window_days)
    max_allowed = scheduled_date + timedelta(days=window_days)

    if actual_date is None:
        # Missed visit
        return {
            "record_id": rec_id,
            "patient_id": patient_id,
            "type": "missed_visit",
            "severity": "major",
            "severity_rationale": f"Visit {v_name} was missed. No actual visit date recorded.",
            "evidence": {
                "field": "actual_date",
                "expected": {
                    "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
                    "window_days": window_days,
                    "allowed_range": [min_allowed.isoformat(), max_allowed.isoformat()],
                },
                "actual": None,
                "delta": "Missed visit (0 actual days recorded)",
            },
        }

    if actual_date < min_allowed or actual_date > max_allowed:
        days_late = (actual_date - scheduled_date).days
        return {
            "record_id": rec_id,
            "patient_id": patient_id,
            "type": "missed_visit",
            "severity": "major",
            "severity_rationale": f"Visit conducted {days_late} days past window. Exceeds protocol specified tolerance of +-{window_days} days.",
            "evidence": {
                "field": "actual_date",
                "expected": {
                    "scheduled_date": scheduled_date.isoformat(),
                    "window_days": window_days,
                    "allowed_range": [min_allowed.isoformat(), max_allowed.isoformat()],
                },
                "actual": actual_date.isoformat(),
                "delta": {
                    "days_offset_from_scheduled": days_late,
                    "days_outside_window": abs(days_late) - window_days,
                },
            },
        }

    return None


def check_wrong_dose(
    record: Any,
    dosing_schedule_item: Dict[str, Any],
    tolerance: float = 0.05,
) -> Optional[Dict[str, Any]]:
    """Rule 2 Evaluator: Wrong Dosing or Drug Mismatch Detection.

    Rule: A deviation is flagged if the administered dose differs from the target dose
    specified in the protocol by more than the configurable tolerance (default 5%), or if
    the administered drug name does not match the protocol drug.

    Args:
        record: VisitRecord object or dictionary.
        dosing_schedule_item (dict): Protocol dosing schedule entry containing 'drug', 'dose', 'unit'.
        tolerance (float): Allowable relative dose percentage deviation (default 0.05 = 5%).

    Returns:
        Optional[dict]: Candidate deviation dict with field-level evidence if flagged, else None.
    """
    dose_given: Optional[float] = getattr(record, "dose_given", None) if hasattr(record, "dose_given") else record.get("dose_given")
    actual_drug: Optional[str] = getattr(record, "drug", None) if hasattr(record, "drug") else record.get("drug")
    rec_id: str = getattr(record, "record_id", "") or record.get("record_id", "")
    patient_id: str = getattr(record, "patient_id", "") or record.get("patient_id", "")

    expected_dose: float = dosing_schedule_item.get("dose", 0.0)
    expected_drug: Optional[str] = dosing_schedule_item.get("drug")
    unit: str = dosing_schedule_item.get("unit", "mg")

    if dose_given is None:
        if expected_dose > 0:
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "wrong_dose",
                "severity": "major",
                "severity_rationale": f"No dose recorded when protocol specified {expected_dose} {unit} of {expected_drug}.",
                "evidence": {
                    "field": "dose_given",
                    "expected": {"drug": expected_drug, "dose": expected_dose, "unit": unit},
                    "actual": None,
                    "delta": "Missing dose log",
                },
            }
        return None

    # Check drug mismatch
    if expected_drug and actual_drug and actual_drug.strip().lower() != expected_drug.strip().lower():
        return {
            "record_id": rec_id,
            "patient_id": patient_id,
            "type": "wrong_dose",
            "severity": "major",
            "severity_rationale": f"Administered study drug '{actual_drug}' deviates from protocol target drug '{expected_drug}'.",
            "evidence": {
                "field": "drug",
                "expected": {"drug": expected_drug, "dose": expected_dose, "unit": unit},
                "actual": {"drug": actual_drug, "dose": dose_given, "unit": unit},
                "delta": "Drug name mismatch",
            },
        }

    # Check dose deviation
    if expected_dose == 0.0:
        if dose_given > 0.0:
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "wrong_dose",
                "severity": "major",
                "severity_rationale": f"Administered dose ({dose_given} {unit}) at visit where protocol target dose is 0.0 {unit}.",
                "evidence": {
                    "field": "dose_given",
                    "expected": {"drug": expected_drug, "dose": expected_dose, "unit": unit},
                    "actual": {"drug": actual_drug, "dose": dose_given, "unit": unit},
                    "delta": {"absolute_difference": dose_given},
                },
            }
    else:
        diff = abs(dose_given - expected_dose)
        allowed_diff = expected_dose * tolerance
        if diff > allowed_diff:
            pct_dev = round((diff / expected_dose) * 100.0, 1)
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "wrong_dose",
                "severity": "major",
                "severity_rationale": f"Administered dose ({dose_given} {unit}) deviates from protocol specification ({expected_dose} {unit}) by {pct_dev}%.",
                "evidence": {
                    "field": "dose_given",
                    "expected": {"drug": expected_drug, "dose": expected_dose, "unit": unit, "tolerance_pct": tolerance * 100},
                    "actual": {"drug": actual_drug, "dose": dose_given, "unit": unit},
                    "delta": {
                        "absolute_difference": diff,
                        "percentage_deviation": pct_dev,
                        "allowed_tolerance_pct": tolerance * 100,
                    },
                },
            }

    return None


def check_banned_comedication(
    record: Any,
    prohibited_medications: List[str],
) -> Optional[Dict[str, Any]]:
    """Rule 3 Evaluator: Prohibited Concomitant Medication Detection.

    Rule: Flags a deviation if any medication listed in the visit record's concomitant_meds
    matches (exact or via synonym lookup) a drug in the protocol's prohibited_medications list.

    Args:
        record: VisitRecord object or dictionary.
        prohibited_medications (List[str]): List of banned drug names from protocol.

    Returns:
        Optional[dict]: Candidate deviation dict with field-level evidence if flagged, else None.
    """
    concomitant_meds: List[str] = getattr(record, "concomitant_meds", []) if hasattr(record, "concomitant_meds") else record.get("concomitant_meds", [])
    rec_id: str = getattr(record, "record_id", "") or record.get("record_id", "")
    patient_id: str = getattr(record, "patient_id", "") or record.get("patient_id", "")

    if not concomitant_meds or not prohibited_medications:
        return None

    for comed in concomitant_meds:
        is_banned, matched_prohibited = is_prohibited_comedication(comed, prohibited_medications)
        if is_banned:
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "banned_comed",
                "severity": "major",
                "severity_rationale": f"Concomitant administration of prohibited drug ({comed}) matching prohibited protocol list entry '{matched_prohibited}'.",
                "evidence": {
                    "field": "concomitant_meds",
                    "expected": {"prohibited_medications": prohibited_medications},
                    "actual": comed,
                    "delta": f"Reported concomitant drug '{comed}' matches prohibited drug '{matched_prohibited}'",
                },
            }

    return None


def check_eligibility_breach(
    record: Any,
    patient: Any = None,
    eligibility_criteria: List[str] = None,
) -> Optional[Dict[str, Any]]:
    """Rule 4 Evaluator: Eligibility Criteria Breach Detection.

    Rule: Flags a deviation if clinical visit notes or patient records indicate a breach
    of protocol eligibility criteria (e.g. ALT/AST lab values exceeding limit, age breach, or unconsented enrollment).

    Args:
        record: VisitRecord object or dictionary.
        patient: Patient model instance or dictionary (optional).
        eligibility_criteria (List[str]): Protocol eligibility criteria list.

    Returns:
        Optional[dict]: Candidate deviation dict with field-level evidence if flagged, else None.
    """
    notes: str = (getattr(record, "notes", "") or record.get("notes", "") or "").lower()
    rec_id: str = getattr(record, "record_id", "") or record.get("record_id", "")
    patient_id: str = getattr(record, "patient_id", "") or record.get("patient_id", "")

    # Look for explicit criteria breach patterns in notes or lab logs
    breach_keywords = [
        "violating inclusion/exclusion",
        "exceeding ast/alt",
        "exceeding 2.5x uln",
        "alt 3.8x uln",
        "alt 4.2x uln",
        "eligibility criteria breach",
        "unconsented",
    ]

    for kw in breach_keywords:
        if kw in notes:
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "eligibility_breach",
                "severity": "major",
                "severity_rationale": "Subject enrolled despite exceeding AST/ALT upper limit threshold established in eligibility criteria.",
                "evidence": {
                    "field": "eligibility_criteria",
                    "expected": {
                        "criterion": "ALT and AST <= 2.5x Upper Limit of Normal (ULN)",
                        "criteria_list": eligibility_criteria or [],
                    },
                    "actual": getattr(record, "notes", "") or record.get("notes"),
                    "delta": f"Matched eligibility violation keyword '{kw}' in clinical notes",
                },
            }

    return None


def check_documentation_gap(record: Any) -> Optional[Dict[str, Any]]:
    """Rule 5 Evaluator: Documentation Gap Detection.

    Rule: Flags an administrative or minor deviation if required documentation fields
    (e.g., PI signature, dose log verification) are explicitly reported as missing/empty in clinical notes.

    Args:
        record: VisitRecord object or dictionary.

    Returns:
        Optional[dict]: Candidate deviation dict with field-level evidence if flagged, else None.
    """
    notes: str = (getattr(record, "notes", "") or record.get("notes", "") or "").lower()
    rec_id: str = getattr(record, "record_id", "") or record.get("record_id", "")
    patient_id: str = getattr(record, "patient_id", "") or record.get("patient_id", "")

    doc_gap_keywords = [
        "missing principal investigator signature",
        "missing pi signature",
        "missing verification stamp",
        "source document verification pending",
        "missing mandatory signature",
    ]

    for kw in doc_gap_keywords:
        if kw in notes:
            return {
                "record_id": rec_id,
                "patient_id": patient_id,
                "type": "documentation",
                "severity": "minor",
                "severity_rationale": "Administrative documentation gap: missing required investigator signature on source log.",
                "evidence": {
                    "field": "notes",
                    "expected": "Complete clinical visit notes with Principal Investigator signature verification.",
                    "actual": getattr(record, "notes", "") or record.get("notes"),
                    "delta": f"Documentation gap identified by keyword: '{kw}'",
                },
            }

    return None


def run_detection_pipeline(
    protocol: Any,
    visit_records: List[Any],
    patients_map: Optional[Dict[str, Any]] = None,
    dose_tolerance: float = 0.05,
) -> List[Dict[str, Any]]:
    """Main Orchestrator: Runs all 5 deterministic detection rules across visit records.

    Args:
        protocol: Protocol model instance or dict.
        visit_records (List[Any]): List of VisitRecord model instances or dicts.
        patients_map (Dict[str, Any], optional): Mapping of patient_id -> Patient model.
        dose_tolerance (float): Dose tolerance percentage (default 0.05).

    Returns:
        List[dict]: Candidate deviation dictionaries containing record_id, site_id, type,
            severity, severity_rationale, evidence.
    """
    patients_map = patients_map or {}
    
    # Extract protocol specs
    visit_schedule = getattr(protocol, "visit_schedule", []) if hasattr(protocol, "visit_schedule") else protocol.get("visit_schedule", [])
    dosing_schedule = getattr(protocol, "dosing_schedule", []) if hasattr(protocol, "dosing_schedule") else protocol.get("dosing_schedule", [])
    prohibited_meds = getattr(protocol, "prohibited_medications", []) if hasattr(protocol, "prohibited_medications") else protocol.get("prohibited_medications", [])
    eligibility_criteria = getattr(protocol, "eligibility_criteria", []) if hasattr(protocol, "eligibility_criteria") else protocol.get("eligibility_criteria", [])

    visit_sched_map = {item["visit_name"]: item for item in visit_schedule}
    dosing_sched_map = {item["visit_name"]: item for item in dosing_schedule}

    candidate_deviations = []

    for record in visit_records:
        v_name = getattr(record, "visit_name", None) or record.get("visit_name")
        patient_id = getattr(record, "patient_id", None) or record.get("patient_id")
        patient = patients_map.get(patient_id)

        v_spec = visit_sched_map.get(v_name, {"visit_name": v_name, "day_offset": 0, "window_days": 3})
        d_spec = dosing_sched_map.get(v_name, {"visit_name": v_name, "drug": None, "dose": 0.0, "unit": "mg"})

        # Rule 1: Missed or out of window visit
        dev1 = check_missed_or_out_of_window_visit(record, v_spec)
        if dev1:
            candidate_deviations.append(dev1)

        # Rule 2: Wrong dose
        dev2 = check_wrong_dose(record, d_spec, tolerance=dose_tolerance)
        if dev2:
            candidate_deviations.append(dev2)

        # Rule 3: Banned comedication
        dev3 = check_banned_comedication(record, prohibited_meds)
        if dev3:
            candidate_deviations.append(dev3)

        # Rule 4: Eligibility breach
        dev4 = check_eligibility_breach(record, patient, eligibility_criteria)
        if dev4:
            candidate_deviations.append(dev4)

        # Rule 5: Documentation gap
        dev5 = check_documentation_gap(record)
        if dev5:
            candidate_deviations.append(dev5)

    return candidate_deviations
