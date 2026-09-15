"""API router for Deviation Detection Engine execution and results retrieval."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.models import Deviation
from src.backend.detection.service import execute_detection_run

router = APIRouter(prefix="/api/detect", tags=["Deviation Detection"])


@router.post("/run", status_code=status.HTTP_200_OK)
def trigger_detection_run(
    protocol_id: str = Query("PROTO-001", description="Protocol ID to analyze"),
    db: Session = Depends(get_db),
):
    """Trigger the deterministic deviation detection engine against visit records.

    Compares all Visit_Record entries against the target Protocol specifications
    and persists detected Deviation rows enriched with field-level supporting evidence.

    Args:
        protocol_id (str): Target protocol ID.
        db (Session): Database session.

    Returns:
        dict: Summary of detection execution results.
    """
    try:
        deviations = execute_detection_run(db, protocol_id=protocol_id)
        
        # Group count by type
        by_type: Dict[str, int] = {}
        for dev in deviations:
            by_type[dev.type] = by_type.get(dev.type, 0) + 1

        return {
            "status": "success",
            "protocol_id": protocol_id,
            "total_deviations_detected": len(deviations),
            "deviations_by_type": by_type,
            "message": f"Detection engine executed successfully. Flagged {len(deviations)} protocol deviations.",
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection run failed: {str(e)}",
        )


@router.get("/results", status_code=status.HTTP_200_OK)
def get_detection_results(
    site_id: str = Query(None, description="Optional site_id filter"),
    deviation_type: str = Query(None, description="Optional deviation type filter"),
    db: Session = Depends(get_db),
):
    """Retrieve all detected protocol deviations with supporting evidence.

    Args:
        site_id (str, optional): Filter by site.
        deviation_type (str, optional): Filter by deviation type.
        db (Session): Database session.

    Returns:
        dict: List of detected deviations and count metadata.
    """
    query = db.query(Deviation)
    if site_id:
        query = query.filter(Deviation.site_id == site_id)
    if deviation_type:
        query = query.filter(Deviation.type == deviation_type)

    deviations = query.all()

    results = []
    for d in deviations:
        results.append({
            "deviation_id": d.deviation_id,
            "record_id": d.record_id,
            "site_id": d.site_id,
            "type": d.type,
            "severity": d.severity,
            "severity_rationale": d.severity_rationale,
            "evidence": d.evidence,
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        })

    return {
        "count": len(results),
        "deviations": results,
    }
