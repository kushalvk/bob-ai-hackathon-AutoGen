"""Database persistence and orchestration service for CAPA report generation.

Follows the same service pattern as risk/service.py — queries deviations
from the database, runs clustering and generation, persists results.
"""

import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from src.backend.capa.generator import (
    cluster_deviations,
    generate_capa_report,
    _get_deviation_attr,
)
from src.backend.llm_client import BaseLLMClient
from src.backend.models import CAPAReport, Deviation

logger = logging.getLogger(__name__)


def generate_and_persist_capa_reports(
    db: Session,
    site_id: Optional[str] = None,
    llm_client: Optional[BaseLLMClient] = None,
    owner: str = "Unassigned",
    due_date: Optional[date] = None,
) -> List[CAPAReport]:
    """Generate CAPA reports from detected deviations and persist to DB.

    Orchestrates:
    1. Querying deviations (optionally filtered by site).
    2. Clustering related deviations (same site + same type + 30-day window).
    3. Generating a CAPAReport per cluster with LLM-authored narratives.
    4. Persisting new CAPA records to the database.

    Args:
        db: Active SQLAlchemy database session.
        site_id: Optional site ID to filter deviations. None = all sites.
        llm_client: Optional LLM client for narrative generation.
            If None, deterministic fallback narratives are used.
        owner: Responsible person for the CAPAs. Defaults to 'Unassigned'.
        due_date: Target completion date. Defaults to 30 days from today.

    Returns:
        List of persisted CAPAReport model instances.
    """
    # 1. Query deviations
    query = db.query(Deviation)
    if site_id:
        query = query.filter(Deviation.site_id == site_id)
    deviations = query.order_by(Deviation.detected_at).all()

    if not deviations:
        logger.info("No deviations found for CAPA generation (site_id=%s).", site_id)
        return []

    # 2. Cluster related deviations
    clusters = cluster_deviations(deviations)
    logger.info(
        "Clustered %d deviations into %d CAPA group(s).",
        len(deviations),
        len(clusters),
    )

    # 3. Determine the next available CAPA counter across all clusters
    existing_count = db.query(CAPAReport).count()
    persisted: List[CAPAReport] = []

    for idx, cluster in enumerate(clusters, start=existing_count + 1):
        site = _get_deviation_attr(cluster[0], "site_id") or "UNKNOWN"
        site_suffix = site.split("-")[1] if "-" in site else site
        capa_id = f"CAPA-{site_suffix}-{idx:03d}"

        # Skip if this CAPA ID already exists
        existing = db.query(CAPAReport).filter(
            CAPAReport.capa_id == capa_id
        ).first()
        if existing:
            logger.info("CAPA %s already exists, skipping.", capa_id)
            persisted.append(existing)
            continue

        report = generate_capa_report(
            cluster=cluster,
            llm_client=llm_client,
            owner=owner,
            due_date=due_date,
            capa_id=capa_id,
        )

        db.add(report)
        persisted.append(report)

    db.commit()
    logger.info("Persisted %d CAPA report(s).", len(persisted))
    return persisted


def get_capa_report(db: Session, capa_id: str) -> Optional[CAPAReport]:
    """Fetch a single CAPA report by its ID.

    Args:
        db: Active SQLAlchemy database session.
        capa_id: CAPA report primary key.

    Returns:
        CAPAReport instance if found, otherwise None.
    """
    return db.query(CAPAReport).filter(CAPAReport.capa_id == capa_id).first()
