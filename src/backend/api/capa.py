"""API router for CAPA (Corrective and Preventive Action) report management.

Provides endpoints for generating, listing, retrieving, and exporting
CAPA reports in Markdown and PDF formats.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.models import CAPAReport
from src.backend.capa.service import generate_and_persist_capa_reports, get_capa_report
from src.backend.capa.export import export_capa_markdown, export_capa_pdf
from src.backend.llm_client import get_llm_client

router = APIRouter(prefix="/api/capa", tags=["CAPA Reports"])


@router.post("/generate", status_code=status.HTTP_200_OK)
def trigger_capa_generation(
    site_id: Optional[str] = Query(None, description="Optional site ID filter"),
    owner: str = Query("Unassigned", description="Responsible owner for the CAPA(s)"),
    due_date: Optional[date] = Query(None, description="Target due date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Generate CAPA reports from detected deviations.

    Clusters related deviations (same site + same type + 30-day window) and
    generates one CAPA report per cluster. LLM narratives are drafted for
    root_cause, corrective_action, and preventive_action fields; all other
    fields are assembled deterministically.

    Args:
        site_id: Optional site ID to limit generation scope.
        owner: Responsible quality monitor. Defaults to 'Unassigned'.
        due_date: Target completion date. Defaults to 30 days from today.
        db: Database session.

    Returns:
        dict: Summary of generated CAPA reports.
    """
    try:
        llm_client = get_llm_client()
        reports = generate_and_persist_capa_reports(
            db=db,
            site_id=site_id,
            llm_client=llm_client,
            owner=owner,
            due_date=due_date,
        )

        results = []
        for r in reports:
            results.append({
                "capa_id": r.capa_id,
                "finding": r.finding,
                "severity": r.severity,
                "deviation_count": len(r.deviation_ids) if r.deviation_ids else 0,
                "owner": r.owner,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "status": r.status,
            })

        return {
            "status": "success",
            "generated_count": len(results),
            "reports": results,
            "message": f"Successfully generated {len(results)} CAPA report(s).",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CAPA generation failed: {str(e)}",
        )


@router.get("/reports", status_code=status.HTTP_200_OK)
def list_capa_reports(
    site_id: Optional[str] = Query(None, description="Optional site ID filter"),
    db: Session = Depends(get_db),
):
    """Retrieve all CAPA reports, optionally filtered by site.

    Args:
        site_id: Optional site ID filter (matches deviation_ids site prefix).
        db: Database session.

    Returns:
        dict: List of CAPA reports with metadata.
    """
    query = db.query(CAPAReport)

    reports = query.all()

    # If site_id filter provided, filter by checking capa_id prefix
    if site_id:
        site_suffix = site_id.split("-")[1] if "-" in site_id else site_id
        reports = [r for r in reports if site_suffix in r.capa_id]

    results = []
    for r in reports:
        results.append({
            "capa_id": r.capa_id,
            "deviation_ids": r.deviation_ids,
            "finding": r.finding,
            "severity": r.severity,
            "severity_rationale": r.severity_rationale,
            "root_cause": r.root_cause,
            "corrective_action": r.corrective_action,
            "preventive_action": r.preventive_action,
            "owner": r.owner,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "status": r.status,
        })

    return {
        "count": len(results),
        "reports": results,
    }


@router.get("/{capa_id}", status_code=status.HTTP_200_OK)
def get_single_capa_report(
    capa_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a single CAPA report by its ID.

    Args:
        capa_id: CAPA report primary key.
        db: Database session.

    Returns:
        dict: Full CAPA report data.

    Raises:
        HTTPException: 404 if CAPA not found.
    """
    report = get_capa_report(db, capa_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CAPA report '{capa_id}' not found.",
        )

    return {
        "capa_id": report.capa_id,
        "deviation_ids": report.deviation_ids,
        "finding": report.finding,
        "severity": report.severity,
        "severity_rationale": report.severity_rationale,
        "root_cause": report.root_cause,
        "corrective_action": report.corrective_action,
        "preventive_action": report.preventive_action,
        "owner": report.owner,
        "due_date": report.due_date.isoformat() if report.due_date else None,
        "status": report.status,
    }


@router.get("/{capa_id}/export", status_code=status.HTTP_200_OK)
def export_capa(
    capa_id: str,
    format: str = Query("markdown", description="Export format: 'markdown' or 'pdf'"),
    db: Session = Depends(get_db),
):
    """Export a CAPA report as Markdown or PDF.

    Args:
        capa_id: CAPA report primary key.
        format: Export format — 'markdown' or 'pdf'.
        db: Database session.

    Returns:
        Response with appropriate content-type and body.

    Raises:
        HTTPException: 404 if CAPA not found, 400 if invalid format.
    """
    report = get_capa_report(db, capa_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CAPA report '{capa_id}' not found.",
        )

    fmt = format.strip().lower()

    if fmt == "markdown":
        md_content = export_capa_markdown(report)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{capa_id}.md"'
            },
        )
    elif fmt == "pdf":
        pdf_bytes = export_capa_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{capa_id}.pdf"'
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format: '{format}'. Use 'markdown' or 'pdf'.",
        )
