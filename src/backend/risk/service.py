"""Database persistence and orchestration service for Site Risk Scoring."""

from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.backend.models import Site, Deviation, Patient, SiteRiskScore
from src.backend.risk.config import RiskConfig, load_risk_config
from src.backend.risk.engine import calculate_site_risk


def compute_and_persist_site_risk_scores(
    db: Session,
    site_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
    config: Optional[RiskConfig] = None,
) -> List[SiteRiskScore]:
    """Calculate site risk scores from deviations and operational metrics, persisting results.

    Orchestrates:
    1. Querying active sites (or specific site if site_id provided).
    2. Aggregating site deviations and leading indicators (turnover, visits, queries, enrollment).
    3. Executing the pure deterministic scoring engine.
    4. Upserting/persisting SiteRiskScore records in the database.

    Args:
        db (Session): Active database session.
        site_id (Optional[str]): Specific site ID to compute, or None for all sites.
        as_of_date (Optional[date]): Target reference date. Defaults to current date.
        config (Optional[RiskConfig]): Injected risk configuration, or loaded from file.

    Returns:
        List[SiteRiskScore]: List of persisted SiteRiskScore model instances.
    """
    cfg = config or load_risk_config()
    ref_date = as_of_date or date.today()
    now_dt = datetime.combine(ref_date, datetime.min.time()) if as_of_date else datetime.now()

    # Query target sites
    query = db.query(Site)
    if site_id:
        query = query.filter(Site.site_id == site_id)
    sites = query.all()

    if not sites:
        return []

    # Pre-fetch all deviations grouped by site
    all_deviations = db.query(Deviation).all()
    deviations_by_site: Dict[str, List[Deviation]] = {}
    for d in all_deviations:
        deviations_by_site.setdefault(d.site_id, []).append(d)

    # Pre-fetch patient counts by site
    all_patients = db.query(Patient).all()
    patients_by_site: Dict[str, int] = {}
    for p in all_patients:
        patients_by_site[p.site_id] = patients_by_site.get(p.site_id, 0) + 1

    persisted_scores: List[SiteRiskScore] = []

    date_str = ref_date.strftime("%Y%m%d")

    for site in sites:
        s_id = site.site_id
        site_devs = deviations_by_site.get(s_id, [])
        enrolled = patients_by_site.get(s_id, 0)

        # Build leading indicators dictionary
        indicators = {
            "enrolled_patients": enrolled,
            "enrollment_target": site.enrollment_target,
            "staff_turnover_rate": site.staff_turnover_rate,
            "last_monitoring_visit_date": site.last_monitoring_visit_date,
            "average_query_resolution_days": getattr(
                site, "average_query_resolution_days", 7.0
            ),
        }

        # Calculate pure deterministic risk score
        risk_result = calculate_site_risk(
            deviations=site_devs,
            leading_indicators=indicators,
            config=cfg,
            as_of_date=ref_date,
        )

        score_val = risk_result["score"]
        factors_json = risk_result["contributing_factors"]

        # Formulate score_id, e.g. RISK-101-20260915
        site_suffix = s_id.split("-")[1] if "-" in s_id else s_id
        score_id = f"RISK-{site_suffix}-{date_str}"

        # Check if record already exists for this site & date, otherwise create
        existing = db.query(SiteRiskScore).filter(
            SiteRiskScore.site_id == s_id,
            SiteRiskScore.score_id == score_id,
        ).first()

        if existing:
            existing.score = score_val
            existing.computed_at = now_dt
            existing.contributing_factors = factors_json
            score_record = existing
        else:
            score_record = SiteRiskScore(
                score_id=score_id,
                site_id=s_id,
                score=score_val,
                computed_at=now_dt,
                contributing_factors=factors_json,
            )
            db.add(score_record)

        persisted_scores.append(score_record)

    db.commit()
    return persisted_scores
