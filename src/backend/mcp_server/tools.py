"""Deterministic tool implementations for the ClinGuard AI MCP Server.

Each tool strictly delegates to existing backend services and database models.
No metrics, risk scores, or deviation findings are generated or guessed by LLMs.
Complete input and output JSON schemas are provided for client contract validation.
"""

from datetime import datetime, date
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from src.backend.database import SessionLocal
from src.backend.models import Deviation, SiteRiskScore, CAPAReport
from src.backend.detection.service import execute_detection_run
from src.backend.risk.service import compute_and_persist_site_risk_scores
from src.backend.capa.generator import generate_capa_report
from src.backend.llm_client import get_llm_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON Schemas for MCP Tools
# ---------------------------------------------------------------------------

RUN_DEVIATION_DETECTION_SCHEMA: Dict[str, Any] = {
    "name": "run_deviation_detection",
    "description": (
        "Run the deterministic deviation detection engine against visit records for a specified "
        "protocol. Evaluates schedule compliance, dose adherence, prohibited concomitant medications, "
        "and eligibility breaches. Returns detected deviations with supporting audit evidence."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "protocol_id": {
                "type": "string",
                "default": "PROTO-001",
                "description": "Unique identifier of the clinical protocol to evaluate.",
            },
            "site_id": {
                "type": "string",
                "description": "Optional site ID filter (e.g., 'SITE-101') to restrict returned deviations.",
            },
        },
        "required": ["protocol_id"],
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "protocol_id": {"type": "string"},
            "site_id_filter": {"type": ["string", "null"]},
            "total_deviations": {"type": "integer"},
            "deviations_by_type": {"type": "object", "additionalProperties": {"type": "integer"}},
            "deviations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "deviation_id": {"type": "string"},
                        "record_id": {"type": ["string", "null"]},
                        "site_id": {"type": "string"},
                        "type": {"type": "string"},
                        "severity": {"type": "string"},
                        "final_severity": {"type": "string"},
                        "severity_rationale": {"type": "string"},
                        "severity_source": {"type": "string"},
                        "evidence": {"type": "object"},
                        "detected_at": {"type": ["string", "null"]},
                    },
                    "required": ["deviation_id", "site_id", "type", "severity", "evidence"],
                },
            },
        },
        "required": ["protocol_id", "total_deviations", "deviations"],
    },
}

GET_SITE_RISK_SCORES_SCHEMA: Dict[str, Any] = {
    "name": "get_site_risk_scores",
    "description": (
        "Retrieve deterministic risk scores (0-100) and 7-factor weighted breakdowns for clinical trial sites. "
        "Factors include major/minor deviation rates, repeated deviation penalties, staff turnover, "
        "monitoring recency, query resolution days, and enrollment deficits. Optionally filter by site_id."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {
                "type": "string",
                "description": "Optional site ID (e.g. 'SITE-101'). If omitted, returns scores for all sites.",
            },
        },
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "site_id_filter": {"type": ["string", "null"]},
            "scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "score_id": {"type": "string"},
                        "site_id": {"type": "string"},
                        "score": {"type": "number"},
                        "risk_tier": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "computed_at": {"type": ["string", "null"]},
                        "contributing_factors": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "factor": {"type": "string"},
                                    "name": {"type": "string"},
                                    "weight": {"type": "number"},
                                    "raw_value": {"type": "number"},
                                    "normalized_score": {"type": "number"},
                                    "contribution": {"type": "number"},
                                },
                            },
                        },
                    },
                    "required": ["score_id", "site_id", "score", "risk_tier", "contributing_factors"],
                },
            },
        },
        "required": ["count", "scores"],
    },
}

GET_DEVIATIONS_SCHEMA: Dict[str, Any] = {
    "name": "get_deviations",
    "description": (
        "Query detected protocol deviations from the database with flexible filtering. "
        "Filter by site ID, severity level (major, minor, administrative), and detection date range."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {
                "type": "string",
                "description": "Filter deviations to a specific site (e.g. 'SITE-101').",
            },
            "severity": {
                "type": "string",
                "enum": ["major", "minor", "administrative"],
                "description": "Filter by assigned severity grade.",
            },
            "date_range": {
                "type": "object",
                "description": "Filter by detection timestamp interval (inclusive).",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Earliest detection date in ISO format (YYYY-MM-DD).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Latest detection date in ISO format (YYYY-MM-DD).",
                    },
                },
            },
        },
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "filters_applied": {
                "type": "object",
                "properties": {
                    "site_id": {"type": ["string", "null"]},
                    "severity": {"type": ["string", "null"]},
                    "date_range": {"type": ["object", "null"]},
                },
            },
            "deviations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "deviation_id": {"type": "string"},
                        "record_id": {"type": ["string", "null"]},
                        "site_id": {"type": "string"},
                        "type": {"type": "string"},
                        "severity": {"type": "string"},
                        "default_severity": {"type": "string"},
                        "final_severity": {"type": "string"},
                        "severity_rationale": {"type": "string"},
                        "severity_source": {"type": "string"},
                        "evidence": {"type": "object"},
                        "detected_at": {"type": ["string", "null"]},
                    },
                    "required": ["deviation_id", "site_id", "type", "severity"],
                },
            },
        },
        "required": ["count", "deviations"],
    },
}

GENERATE_OR_FETCH_CAPA_SCHEMA: Dict[str, Any] = {
    "name": "generate_or_fetch_capa",
    "description": (
        "Retrieve an existing Corrective and Preventive Action (CAPA) report by capa_id, "
        "or locate/generate a CAPA report addressing a specific deviation_id. Returns full "
        "finding summary, severity, root cause analysis, corrective/preventive actions, owner, and due date."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "capa_id": {
                "type": "string",
                "description": "Primary key ID of an existing CAPA report (e.g. 'CAPA-101-001').",
            },
            "deviation_id": {
                "type": "string",
                "description": (
                    "Deviation ID (e.g. 'DEV-0001'). If provided, fetches an existing CAPA containing "
                    "this deviation or generates a new CAPA report if none exists yet."
                ),
            },
        },
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["fetched_by_capa_id", "fetched_existing_by_deviation", "generated_new", "not_found"],
            },
            "capa_id": {"type": ["string", "null"]},
            "deviation_ids": {"type": "array", "items": {"type": "string"}},
            "finding": {"type": "string"},
            "severity": {"type": "string"},
            "severity_rationale": {"type": "string"},
            "root_cause": {"type": "string"},
            "corrective_action": {"type": "string"},
            "preventive_action": {"type": "string"},
            "owner": {"type": "string"},
            "due_date": {"type": ["string", "null"]},
            "status": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

def run_deviation_detection(
    protocol_id: str = "PROTO-001",
    site_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Execute deterministic deviation detection against visit records and return findings.

    Args:
        protocol_id (str): Clinical trial protocol identifier. Defaults to 'PROTO-001'.
        site_id (Optional[str]): If specified, restricts returned deviations to this site.
        db (Optional[Session]): Active SQLAlchemy session; if None, opens a session.

    Returns:
        Dict[str, Any]: Formatted result dictionary conforming to RUN_DEVIATION_DETECTION_SCHEMA.
    """
    session = db or SessionLocal()
    should_close = db is None

    try:
        deviations = execute_detection_run(session, protocol_id=protocol_id)

        if site_id:
            deviations = [d for d in deviations if d.site_id == site_id]

        by_type: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []

        for d in deviations:
            by_type[d.type] = by_type.get(d.type, 0) + 1
            items.append({
                "deviation_id": d.deviation_id,
                "record_id": d.record_id,
                "site_id": d.site_id,
                "type": d.type,
                "severity": d.severity,
                "default_severity": getattr(d, "default_severity", d.severity),
                "final_severity": getattr(d, "final_severity", d.severity),
                "severity_rationale": d.severity_rationale or "",
                "severity_source": getattr(d, "severity_source", "deterministic"),
                "evidence": d.evidence or {},
                "detected_at": d.detected_at.isoformat() if d.detected_at else None,
            })

        return {
            "protocol_id": protocol_id,
            "site_id_filter": site_id,
            "total_deviations": len(items),
            "deviations_by_type": by_type,
            "deviations": items,
        }
    finally:
        if should_close:
            session.close()


def get_site_risk_scores(
    site_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Retrieve current site risk scores and contributing factor breakdowns.

    Args:
        site_id (Optional[str]): Optional site identifier to query specifically.
        db (Optional[Session]): Active SQLAlchemy session; if None, opens a session.

    Returns:
        Dict[str, Any]: Formatted risk scores conforming to GET_SITE_RISK_SCORES_SCHEMA.
    """
    session = db or SessionLocal()
    should_close = db is None

    try:
        query = session.query(SiteRiskScore)
        if site_id:
            query = query.filter(SiteRiskScore.site_id == site_id)

        scores = query.order_by(SiteRiskScore.score.desc()).all()

        # If no scores exist yet, compute and persist them
        if not scores:
            scores = compute_and_persist_site_risk_scores(session, site_id=site_id)

        items: List[Dict[str, Any]] = []
        for s in scores:
            score_val = round(float(s.score), 2)
            if score_val >= 60.0:
                tier = "High"
            elif score_val >= 35.0:
                tier = "Medium"
            else:
                tier = "Low"

            items.append({
                "score_id": s.score_id,
                "site_id": s.site_id,
                "score": score_val,
                "risk_tier": tier,
                "computed_at": s.computed_at.isoformat() if s.computed_at else None,
                "contributing_factors": s.contributing_factors or [],
            })

        return {
            "count": len(items),
            "site_id_filter": site_id,
            "scores": items,
        }
    finally:
        if should_close:
            session.close()


def get_deviations(
    site_id: Optional[str] = None,
    severity: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Query deviations from the database with flexible filtering.

    Args:
        site_id (Optional[str]): Filter by clinical site ID.
        severity (Optional[str]): Filter by severity level ('major', 'minor', 'administrative').
        date_range (Optional[Dict[str, str]]): Optional dict with 'start_date' and/or 'end_date' (YYYY-MM-DD).
        db (Optional[Session]): Active SQLAlchemy session; if None, opens a session.

    Returns:
        Dict[str, Any]: Filtered deviations matching GET_DEVIATIONS_SCHEMA.
    """
    session = db or SessionLocal()
    should_close = db is None

    try:
        query = session.query(Deviation)

        if site_id:
            query = query.filter(Deviation.site_id == site_id)

        if severity:
            sev_clean = severity.strip().lower()
            query = query.filter(
                (Deviation.final_severity == sev_clean) | (Deviation.severity == sev_clean)
            )

        if date_range:
            start_str = date_range.get("start_date")
            end_str = date_range.get("end_date")

            if start_str:
                start_dt = datetime.fromisoformat(start_str)
                query = query.filter(Deviation.detected_at >= start_dt)
            if end_str:
                end_dt = datetime.fromisoformat(end_str)
                # If date-only string was given, compare up to end of that day
                if len(end_str) <= 10:
                    end_dt = datetime.combine(end_dt.date(), datetime.max.time())
                query = query.filter(Deviation.detected_at <= end_dt)

        deviations = query.order_by(Deviation.detected_at.desc()).all()

        items: List[Dict[str, Any]] = []
        for d in deviations:
            items.append({
                "deviation_id": d.deviation_id,
                "record_id": d.record_id,
                "site_id": d.site_id,
                "type": d.type,
                "severity": d.severity,
                "default_severity": getattr(d, "default_severity", d.severity),
                "final_severity": getattr(d, "final_severity", d.severity),
                "severity_rationale": d.severity_rationale or "",
                "severity_source": getattr(d, "severity_source", "deterministic"),
                "evidence": d.evidence or {},
                "detected_at": d.detected_at.isoformat() if d.detected_at else None,
            })

        return {
            "count": len(items),
            "filters_applied": {
                "site_id": site_id,
                "severity": severity,
                "date_range": date_range,
            },
            "deviations": items,
        }
    finally:
        if should_close:
            session.close()


def generate_or_fetch_capa(
    capa_id: Optional[str] = None,
    deviation_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Retrieve an existing CAPA report or generate one for a specified deviation.

    Args:
        capa_id (Optional[str]): Primary key ID of an existing CAPA report.
        deviation_id (Optional[str]): Deviation ID to locate or generate a CAPA for.
        db (Optional[Session]): Active SQLAlchemy session; if None, opens a session.

    Returns:
        Dict[str, Any]: CAPA details conforming to GENERATE_OR_FETCH_CAPA_SCHEMA.
    """
    if not capa_id and not deviation_id:
        return {
            "action": "not_found",
            "capa_id": None,
            "deviation_ids": [],
            "finding": "",
            "severity": "",
            "severity_rationale": "",
            "root_cause": "",
            "corrective_action": "",
            "preventive_action": "",
            "owner": "",
            "due_date": None,
            "status": "",
            "message": "Either 'capa_id' or 'deviation_id' must be specified.",
        }

    session = db or SessionLocal()
    should_close = db is None

    try:
        # Case 1: Lookup directly by capa_id
        if capa_id:
            capa = session.query(CAPAReport).filter(CAPAReport.capa_id == capa_id).first()
            if capa:
                return {
                    "action": "fetched_by_capa_id",
                    "capa_id": capa.capa_id,
                    "deviation_ids": capa.deviation_ids or [],
                    "finding": getattr(capa, "finding", "") or "",
                    "severity": getattr(capa, "severity", "minor") or "minor",
                    "severity_rationale": getattr(capa, "severity_rationale", "") or "",
                    "root_cause": capa.root_cause or "",
                    "corrective_action": capa.corrective_action or "",
                    "preventive_action": capa.preventive_action or "",
                    "owner": capa.owner or "",
                    "due_date": capa.due_date.isoformat() if capa.due_date else None,
                    "status": capa.status or "open",
                    "message": f"Successfully retrieved CAPA report '{capa_id}'.",
                }
            return {
                "action": "not_found",
                "capa_id": capa_id,
                "deviation_ids": [],
                "finding": "",
                "severity": "",
                "severity_rationale": "",
                "root_cause": "",
                "corrective_action": "",
                "preventive_action": "",
                "owner": "",
                "due_date": None,
                "status": "",
                "message": f"CAPA report '{capa_id}' not found.",
            }

        # Case 2: Find or generate by deviation_id
        dev = session.query(Deviation).filter(Deviation.deviation_id == deviation_id).first()
        if not dev:
            return {
                "action": "not_found",
                "capa_id": None,
                "deviation_ids": [deviation_id] if deviation_id else [],
                "finding": "",
                "severity": "",
                "severity_rationale": "",
                "root_cause": "",
                "corrective_action": "",
                "preventive_action": "",
                "owner": "",
                "due_date": None,
                "status": "",
                "message": f"Deviation '{deviation_id}' not found in database.",
            }

        # Check if an existing CAPA already covers this deviation
        all_capas = session.query(CAPAReport).all()
        for c in all_capas:
            if c.deviation_ids and deviation_id in c.deviation_ids:
                return {
                    "action": "fetched_existing_by_deviation",
                    "capa_id": c.capa_id,
                    "deviation_ids": c.deviation_ids,
                    "finding": getattr(c, "finding", "") or "",
                    "severity": getattr(c, "severity", "minor") or "minor",
                    "severity_rationale": getattr(c, "severity_rationale", "") or "",
                    "root_cause": c.root_cause or "",
                    "corrective_action": c.corrective_action or "",
                    "preventive_action": c.preventive_action or "",
                    "owner": c.owner or "",
                    "due_date": c.due_date.isoformat() if c.due_date else None,
                    "status": c.status or "open",
                    "message": f"Found existing CAPA '{c.capa_id}' covering deviation '{deviation_id}'.",
                }

        # If none exists, generate a new CAPA report for this deviation
        site_suffix = dev.site_id.split("-")[1] if "-" in dev.site_id else dev.site_id
        existing_count = session.query(CAPAReport).count()
        new_capa_id = f"CAPA-{site_suffix}-{existing_count + 1:03d}"

        llm_client = get_llm_client()
        new_capa = generate_capa_report(
            cluster=[dev],
            llm_client=llm_client,
            owner="Quality Assurance Manager",
            capa_id=new_capa_id,
        )

        session.add(new_capa)
        session.commit()
        session.refresh(new_capa)

        return {
            "action": "generated_new",
            "capa_id": new_capa.capa_id,
            "deviation_ids": new_capa.deviation_ids or [],
            "finding": getattr(new_capa, "finding", "") or "",
            "severity": getattr(new_capa, "severity", "minor") or "minor",
            "severity_rationale": getattr(new_capa, "severity_rationale", "") or "",
            "root_cause": new_capa.root_cause or "",
            "corrective_action": new_capa.corrective_action or "",
            "preventive_action": new_capa.preventive_action or "",
            "owner": new_capa.owner or "",
            "due_date": new_capa.due_date.isoformat() if new_capa.due_date else None,
            "status": new_capa.status or "open",
            "message": f"Generated new CAPA report '{new_capa.capa_id}' for deviation '{deviation_id}'.",
        }
    finally:
        if should_close:
            session.close()
