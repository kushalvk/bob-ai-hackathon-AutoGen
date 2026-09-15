"""Pure deterministic Site Risk Scoring Engine.

Calculates composite 0-100 site risk scores based on a 7-factor weighted formula
with full mathematical transparency and contributing factor breakdown.
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional, Sequence, Union

from src.backend.risk.config import RiskConfig, load_risk_config
from src.backend.risk.normalizers import (
    normalize_major_deviation_rate,
    normalize_minor_deviation_rate,
    normalize_deviation_trend,
    normalize_query_resolution_time,
    normalize_enrollment_target,
    normalize_staff_turnover,
    normalize_days_since_monitoring,
)


def _get_severity(deviation: Any) -> str:
    """Extract final severity string from deviation dict or ORM model."""
    if isinstance(deviation, dict):
        return str(
            deviation.get("final_severity")
            or deviation.get("severity")
            or deviation.get("default_severity", "minor")
        ).lower()
    return str(
        getattr(deviation, "final_severity", None)
        or getattr(deviation, "severity", None)
        or getattr(deviation, "default_severity", "minor")
    ).lower()


def _get_date(deviation: Any) -> Optional[date]:
    """Extract occurrence date from deviation dict or ORM model."""
    val = None
    if isinstance(deviation, dict):
        val = deviation.get("detected_at") or deviation.get("date")
    else:
        val = getattr(deviation, "detected_at", None) or getattr(deviation, "date", None)

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).date()
        except Exception:
            return None
    return None


def calculate_site_risk(
    deviations: Sequence[Any],
    leading_indicators: Dict[str, Any],
    config: Optional[RiskConfig] = None,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Calculate composite deterministic risk score (0-100) and contributing factor breakdown.

    Pure mathematical function without database or network I/O. Given a site's deviations
    and operational leading indicators, evaluates the 7 factors specified in the ClinGuard formula:
    1. Major deviation rate (30%)
    2. Minor/administrative deviation rate (10%)
    3. Deviation trend (15%)
    4. Query resolution time (15%)
    5. Enrollment vs. target (10%)
    6. Staff turnover rate (10%)
    7. Days since last monitoring visit (10%)

    Args:
        deviations (Sequence[Any]): List of deviations (dict or ORM model instances).
        leading_indicators (dict): Operational site indicators containing:
            - 'enrolled_patients' (int): Active enrolled patient count.
            - 'enrollment_target' (int): Planned target enrollment.
            - 'staff_turnover_rate' (float): Annual turnover rate (0.0 - 1.0).
            - 'days_since_last_monitoring_visit' (int, optional): Days since last CRA visit.
            - 'last_monitoring_visit_date' (date, optional): Used if days not supplied.
            - 'average_query_resolution_days' (float, optional): EDC query resolution time.
        config (Optional[RiskConfig]): Risk formula weights and normalization configuration.
            Defaults to loaded configuration from `risk_weights.json`.
        as_of_date (Optional[date]): Target reference date for recency calculations.

    Returns:
        dict: Transparent risk evaluation result containing:
            - 'score' (float): Composite score in range [0.0, 100.0].
            - 'contributing_factors' (list[dict]): Detailed factor-by-factor breakdown.
    """
    cfg = config or load_risk_config()
    ref_date = as_of_date or date.today()

    enrolled = int(leading_indicators.get("enrolled_patients", 1))
    enrolled_count = max(enrolled, 1)

    # 1. Major Deviations
    major_devs = [d for d in deviations if _get_severity(d) == "major"]
    raw_major_rate = round(len(major_devs) / float(enrolled_count), 3)
    major_cfg = cfg.factors["major_deviation_rate"]
    norm_major = normalize_major_deviation_rate(raw_major_rate, major_cfg.parameters)
    contrib_major = round(norm_major * major_cfg.weight, 2)

    # 2. Minor/Administrative Deviations
    minor_devs = [d for d in deviations if _get_severity(d) != "major"]
    raw_minor_rate = round(len(minor_devs) / float(enrolled_count), 3)
    minor_cfg = cfg.factors["minor_deviation_rate"]
    norm_minor = normalize_minor_deviation_rate(raw_minor_rate, minor_cfg.parameters)
    contrib_minor = round(norm_minor * minor_cfg.weight, 2)

    # 3. Deviation Trend
    dev_dates = [_get_date(d) for d in deviations if _get_date(d) is not None]
    trend_cfg = cfg.factors["deviation_trend"]
    norm_trend, raw_trend_ratio = normalize_deviation_trend(
        dev_dates, trend_cfg.parameters, as_of_date=ref_date
    )
    contrib_trend = round(norm_trend * trend_cfg.weight, 2)

    # 4. Query Resolution Time
    raw_query_days = float(leading_indicators.get("average_query_resolution_days", 7.0))
    query_cfg = cfg.factors["query_resolution_time"]
    norm_query = normalize_query_resolution_time(raw_query_days, query_cfg.parameters)
    contrib_query = round(norm_query * query_cfg.weight, 2)

    # 5. Enrollment vs. Target
    target = int(leading_indicators.get("enrollment_target", enrolled_count))
    enroll_cfg = cfg.factors["enrollment_vs_target"]
    norm_enroll, raw_enroll_ratio = normalize_enrollment_target(
        enrolled, target, enroll_cfg.parameters
    )
    contrib_enroll = round(norm_enroll * enroll_cfg.weight, 2)

    # 6. Staff Turnover Rate
    raw_turnover = float(leading_indicators.get("staff_turnover_rate", 0.0))
    turnover_cfg = cfg.factors["staff_turnover_rate"]
    norm_turnover = normalize_staff_turnover(raw_turnover, turnover_cfg.parameters)
    contrib_turnover = round(norm_turnover * turnover_cfg.weight, 2)

    # 7. Days Since Last Monitoring Visit
    if "days_since_last_monitoring_visit" in leading_indicators:
        raw_monitoring_days = int(leading_indicators["days_since_last_monitoring_visit"])
    elif leading_indicators.get("last_monitoring_visit_date"):
        v_date = leading_indicators["last_monitoring_visit_date"]
        if isinstance(v_date, str):
            v_date = datetime.fromisoformat(v_date).date()
        raw_monitoring_days = max(0, (ref_date - v_date).days)
    else:
        raw_monitoring_days = 30  # Default neutral routine monitoring

    monitoring_cfg = cfg.factors["days_since_last_monitoring_visit"]
    norm_monitoring = normalize_days_since_monitoring(
        raw_monitoring_days, monitoring_cfg.parameters
    )
    contrib_monitoring = round(norm_monitoring * monitoring_cfg.weight, 2)

    contributing_factors = [
        {
            "factor": "major_deviation_rate",
            "name": major_cfg.name,
            "weight": major_cfg.weight,
            "raw_value": raw_major_rate,
            "normalized_score": norm_major,
            "contribution": contrib_major,
        },
        {
            "factor": "minor_deviation_rate",
            "name": minor_cfg.name,
            "weight": minor_cfg.weight,
            "raw_value": raw_minor_rate,
            "normalized_score": norm_minor,
            "contribution": contrib_minor,
        },
        {
            "factor": "deviation_trend",
            "name": trend_cfg.name,
            "weight": trend_cfg.weight,
            "raw_value": raw_trend_ratio,
            "normalized_score": norm_trend,
            "contribution": contrib_trend,
        },
        {
            "factor": "query_resolution_time",
            "name": query_cfg.name,
            "weight": query_cfg.weight,
            "raw_value": raw_query_days,
            "normalized_score": norm_query,
            "contribution": contrib_query,
        },
        {
            "factor": "enrollment_vs_target",
            "name": enroll_cfg.name,
            "weight": enroll_cfg.weight,
            "raw_value": raw_enroll_ratio,
            "normalized_score": norm_enroll,
            "contribution": contrib_enroll,
        },
        {
            "factor": "staff_turnover_rate",
            "name": turnover_cfg.name,
            "weight": turnover_cfg.weight,
            "raw_value": raw_turnover,
            "normalized_score": norm_turnover,
            "contribution": contrib_turnover,
        },
        {
            "factor": "days_since_last_monitoring_visit",
            "name": monitoring_cfg.name,
            "weight": monitoring_cfg.weight,
            "raw_value": float(raw_monitoring_days),
            "normalized_score": norm_monitoring,
            "contribution": contrib_monitoring,
        },
    ]

    total_score = sum(f["contribution"] for f in contributing_factors)
    clamped_total = max(0.0, min(100.0, round(total_score, 1)))

    return {
        "score": clamped_total,
        "contributing_factors": contributing_factors,
    }
