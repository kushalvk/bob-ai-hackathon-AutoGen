"""API router for deterministic Site Risk Scoring execution and results retrieval."""

from datetime import date
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.models import SiteRiskScore, Site
from src.backend.risk.service import compute_and_persist_site_risk_scores

router = APIRouter(prefix="/api/risk", tags=["Site Risk Scoring"])


@router.post("/compute", status_code=status.HTTP_200_OK)
def compute_risk_scores(
    site_id: Optional[str] = Query(None, description="Optional site ID to compute specifically"),
    as_of_date: Optional[date] = Query(None, description="Target evaluation reference date"),
    db: Session = Depends(get_db),
):
    """Recompute deterministic site risk scores (0-100) and persist Site_Risk_Score rows.

    Evaluates the 7-factor weighted formula across protocol deviations and leading operational
    indicators (staff turnover, monitoring recency, query resolution time, enrollment deficit).
    Each score includes a full, transparent breakdown of contributing factors.

    Args:
        site_id (Optional[str]): Specific site ID or None for all sites.
        as_of_date (Optional[date]): Calculation reference date.
        db (Session): Database session.

    Returns:
        dict: Summary of computed site risk scores and contributing factor breakdowns.
    """
    try:
        scores = compute_and_persist_site_risk_scores(
            db=db,
            site_id=site_id,
            as_of_date=as_of_date,
        )

        results = []
        for s in scores:
            results.append({
                "score_id": s.score_id,
                "site_id": s.site_id,
                "score": s.score,
                "computed_at": s.computed_at.isoformat() if s.computed_at else None,
                "contributing_factors": s.contributing_factors,
            })

        return {
            "status": "success",
            "computed_count": len(results),
            "scores": results,
            "message": f"Successfully computed deterministic risk scores for {len(results)} site(s).",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk scoring computation failed: {str(e)}",
        )


@router.get("/scores", status_code=status.HTTP_200_OK)
def get_risk_scores(
    site_id: Optional[str] = Query(None, description="Optional site ID filter"),
    db: Session = Depends(get_db),
):
    """Retrieve persisted Site Risk Scores and their transparent contributing factor breakdowns.

    Args:
        site_id (Optional[str]): Optional site ID filter.
        db (Session): Database session.

    Returns:
        dict: List of site risk scores.
    """
    query = db.query(SiteRiskScore)
    if site_id:
        query = query.filter(SiteRiskScore.site_id == site_id)

    scores = query.order_by(SiteRiskScore.score.desc()).all()

    results = []
    for s in scores:
        results.append({
            "score_id": s.score_id,
            "site_id": s.site_id,
            "score": s.score,
            "computed_at": s.computed_at.isoformat() if s.computed_at else None,
            "contributing_factors": s.contributing_factors,
        })

    return {
        "count": len(results),
        "scores": results,
    }
