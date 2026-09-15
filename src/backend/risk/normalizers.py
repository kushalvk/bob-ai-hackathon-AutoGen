"""Pure normalization functions mapping raw clinical site metrics to 0-100 risk sub-scores.

Every function is deterministic, mathematical, boundary-clamped between 0.0 and 100.0,
and thoroughly documented with ICH E6(R2) / TransCelerate RBM clinical rationale.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Sequence, Tuple


def normalize_major_deviation_rate(rate: float, params: Dict[str, Any]) -> float:
    """Normalize major protocol deviation rate to a 0-100 risk sub-score.

    Clinical Rationale:
        Major deviations compromise subject safety, informed consent rights, or the
        integrity and reliability of trial endpoints (ICH E6(R2) 5.20). In clinical trial
        risk-based monitoring (RBM), a major deviation rate exceeding 0.50 deviations
        per enrolled subject represents a severe breakdown of site protocol compliance.

    Normalization Method:
        Clinical Threshold Linear Ramp with Upper Bound Clamping.
        - min_rate (default 0.0): 0.0 subscore (zero major deviations).
        - max_threshold_rate (default 0.50): 100.0 subscore (critical risk threshold).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        rate (float): Major deviations per enrolled patient (or raw rate).
        params (dict): Config parameters containing 'min_rate' and 'max_threshold_rate'.

    Returns:
        float: Normalized risk sub-score in range [0.0, 100.0].
    """
    if rate <= 0.0:
        return 0.0

    min_rate = float(params.get("min_rate", 0.0))
    max_rate = float(params.get("max_threshold_rate", 0.50))

    if max_rate <= min_rate:
        return 100.0 if rate > min_rate else 0.0

    normalized = ((rate - min_rate) / (max_rate - min_rate)) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))


def normalize_minor_deviation_rate(rate: float, params: Dict[str, Any]) -> float:
    """Normalize minor and administrative deviation rate to a 0-100 risk sub-score.

    Clinical Rationale:
        Minor deviations (e.g. out-of-window visits without clinical impact) and administrative
        gaps (e.g. missing signature dates on logs) do not immediately jeopardize patient safety.
        However, a high cumulative frequency reflects carelessness, study coordinator fatigue,
        or systemic process errors that precede major non-compliance.

    Normalization Method:
        Clinical Threshold Linear Ramp with Upper Bound Clamping.
        - min_rate (default 0.0): 0.0 subscore.
        - max_threshold_rate (default 1.50): 100.0 subscore (>= 1.5 minor deviations per patient).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        rate (float): Minor/administrative deviations per enrolled patient.
        params (dict): Config parameters containing 'min_rate' and 'max_threshold_rate'.

    Returns:
        float: Normalized risk sub-score in range [0.0, 100.0].
    """
    if rate <= 0.0:
        return 0.0

    min_rate = float(params.get("min_rate", 0.0))
    max_rate = float(params.get("max_threshold_rate", 1.50))

    if max_rate <= min_rate:
        return 100.0 if rate > min_rate else 0.0

    normalized = ((rate - min_rate) / (max_rate - min_rate)) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))


def normalize_deviation_trend(
    deviation_dates: Sequence[datetime | date],
    params: Dict[str, Any],
    as_of_date: Optional[date] = None,
) -> Tuple[float, float]:
    """Normalize deviation trajectory (worsening vs. improving) to a 0-100 risk sub-score.

    Clinical Rationale:
        A site with improving deviation frequency (fewer deviations recently than in prior periods)
        demonstrates corrective action responsiveness. Conversely, a site where deviation rates
        are accelerating (worsening) signals uncontained operational drift and high forward-looking risk.

    Normalization Method:
        Directional Ratio Mapping with Baseline Center.
        - If 0 deviations exist: subscore = 0.0 (no risk), trend ratio = 0.0.
        - Split observation period into recent period vs. prior period.
        - trend_ratio = (recent_count - prior_count) / (recent_count + prior_count) in [-1.0, +1.0].
        - trend_ratio = -1.0 -> 0.0 subscore (completely improving, zero recent deviations).
        - trend_ratio =  0.0 -> 50.0 subscore (neutral / stable trajectory).
        - trend_ratio = +1.0 -> 100.0 subscore (critically worsening, all recent).
        Formula: subscore = baseline_neutral_score (50.0) + (trend_ratio * 50.0), clamped [0, 100].

    Args:
        deviation_dates (Sequence[datetime | date]): Collection of timestamps when deviations occurred.
        params (dict): Config parameters containing 'recent_window_days' and 'baseline_neutral_score'.
        as_of_date (Optional[date]): Target reference date for recency calculation.

    Returns:
        Tuple[float, float]: (normalized_subscore [0.0 - 100.0], trend_ratio [-1.0 - +1.0]).
    """
    if not deviation_dates:
        return 0.0, 0.0

    recent_window_days = int(params.get("recent_window_days", 60))
    baseline = float(params.get("baseline_neutral_score", 50.0))

    # Convert all to dates
    parsed_dates = []
    for d in deviation_dates:
        if isinstance(d, datetime):
            parsed_dates.append(d.date())
        elif isinstance(d, date):
            parsed_dates.append(d)

    if not parsed_dates:
        return 0.0, 0.0

    ref_date = as_of_date or max(parsed_dates)
    recent_cutoff = ref_date - timedelta(days=recent_window_days)
    prior_cutoff = ref_date - timedelta(days=recent_window_days * 2)

    recent_count = sum(1 for d in parsed_dates if d >= recent_cutoff)
    prior_count = sum(1 for d in parsed_dates if prior_cutoff <= d < recent_cutoff)

    # If all deviations fall outside the 2x recent window (e.g. historical data),
    # fallback to chronological timeline midpoint splitting
    if (recent_count + prior_count) == 0:
        min_dt = min(parsed_dates)
        max_dt = max(parsed_dates)
        if min_dt == max_dt:
            # Single point in time
            return baseline, 0.0
        midpoint = min_dt + (max_dt - min_dt) / 2
        prior_count = sum(1 for d in parsed_dates if d < midpoint)
        recent_count = sum(1 for d in parsed_dates if d >= midpoint)

    total = recent_count + prior_count
    if total == 0:
        return baseline, 0.0

    ratio = (recent_count - prior_count) / float(total)
    subscore = baseline + (ratio * 50.0)
    clamped_subscore = max(0.0, min(100.0, round(subscore, 2)))
    return clamped_subscore, round(ratio, 3)


def normalize_query_resolution_time(days: float, params: Dict[str, Any]) -> float:
    """Normalize average query resolution time to a 0-100 risk sub-score.

    Clinical Rationale:
        Electronic Data Capture (EDC) queries must be addressed promptly by site coordinators
        to maintain clinical data currency and safety signal detection. Standard Good Clinical
        Practice (GCP) SLA requires query resolution within 5 to 7 days. Sites averaging >= 30 days
        block interim analyses, data lock, and delay safety reviews.

    Normalization Method:
        Clinical Benchmark Min-Max Linear Interpolation.
        - optimal_days (default 5.0): 0.0 subscore (within standard SLA).
        - critical_days (default 30.0): 100.0 subscore (critically delinquent query response).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        days (float): Average calendar days to resolve queries.
        params (dict): Config parameters containing 'optimal_days' and 'critical_days'.

    Returns:
        float: Normalized risk sub-score in range [0.0, 100.0].
    """
    if days <= 0.0:
        return 0.0

    optimal_days = float(params.get("optimal_days", 5.0))
    critical_days = float(params.get("critical_days", 30.0))

    if days <= optimal_days:
        return 0.0
    if days >= critical_days:
        return 100.0

    span = critical_days - optimal_days
    if span <= 0:
        return 100.0

    normalized = ((days - optimal_days) / span) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))


def normalize_enrollment_target(
    actual_enrolled: int, target: int, params: Dict[str, Any]
) -> Tuple[float, float]:
    """Normalize enrollment vs. target recruitment deficit to a 0-100 risk sub-score.

    Clinical Rationale:
        Sites that substantially lag recruitment milestones threaten study statistical power,
        extend trial completion timelines, and often experience coordinator turnover and demotivation.
        Under-enrollment (high deficit) is a key operational risk in TransCelerate RBM frameworks.

    Normalization Method:
        Recruitment Deficit Linear Ramp.
        - actual_enrolled >= target: 0.0 deficit, 0.0 subscore (target met or exceeded).
        - actual_enrolled == 0: 100.0% deficit, 100.0 subscore (no enrollment).
        - deficit = max(0.0, 1.0 - (actual_enrolled / target)).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        actual_enrolled (int): Number of participants enrolled at the site.
        target (int): Protocol planned enrollment target for the site.
        params (dict): Config parameters.

    Returns:
        Tuple[float, float]: (normalized_subscore [0.0 - 100.0], fulfillment_ratio).
    """
    if target <= 0:
        # If no target specified or zero, neutral 0 risk
        return 0.0, 1.0

    ratio = actual_enrolled / float(target)
    if ratio >= 1.0:
        return 0.0, round(ratio, 3)

    deficit = max(0.0, 1.0 - ratio)
    subscore = deficit * 100.0
    return max(0.0, min(100.0, round(subscore, 2))), round(ratio, 3)


def normalize_staff_turnover(rate: float, params: Dict[str, Any]) -> float:
    """Normalize annual staff turnover rate to a 0-100 risk sub-score.

    Clinical Rationale:
        Coordinator and sub-investigator turnover is the leading operational predictor
        of trial protocol non-compliance. When experienced staff depart, new personnel often
        administer incorrect doses, miss tightly scheduled visits, or fail to log concomitant drugs.
        A turnover rate >= 30% indicates severe institutional instability.

    Normalization Method:
        Clinical Benchmark Linear Ramp with Saturation.
        - min_turnover (default 0.0): 0.0 subscore (zero turnover).
        - critical_turnover (default 0.30): 100.0 subscore (>= 30% annual turnover).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        rate (float): Staff turnover rate (0.0 to 1.0).
        params (dict): Config parameters containing 'min_turnover' and 'critical_turnover'.

    Returns:
        float: Normalized risk sub-score in range [0.0, 100.0].
    """
    if rate <= 0.0:
        return 0.0

    min_turnover = float(params.get("min_turnover", 0.0))
    critical_turnover = float(params.get("critical_turnover", 0.30))

    if rate >= critical_turnover:
        return 100.0

    span = critical_turnover - min_turnover
    if span <= 0:
        return 100.0

    normalized = ((rate - min_turnover) / span) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))


def normalize_days_since_monitoring(
    days: int, params: Dict[str, Any]
) -> float:
    """Normalize elapsed calendar days since last monitoring visit to a 0-100 risk sub-score.

    Clinical Rationale:
        Clinical Research Associate (CRA) monitoring visits verify source data integrity,
        drug accountability, and regulatory documentation. An interval <= 30 days is standard
        routine monitoring. An interval >= 90 days represents overdue monitoring, where deviations
        may go unflagged and uncorrected for extended periods.

    Normalization Method:
        Monitoring Recency Min-Max Linear Interpolation.
        - optimal_days (default 30): 0.0 subscore (recently monitored within routine window).
        - critical_days (default 90): 100.0 subscore (overdue monitoring >= 90 days).
        - Clamped linearly between 0.0 and 100.0.

    Args:
        days (int): Elapsed days since last CRA monitoring visit.
        params (dict): Config parameters containing 'optimal_days' and 'critical_days'.

    Returns:
        float: Normalized risk sub-score in range [0.0, 100.0].
    """
    if days <= 0:
        return 0.0

    optimal_days = int(params.get("optimal_days", 30))
    critical_days = int(params.get("critical_days", 90))

    if days <= optimal_days:
        return 0.0
    if days >= critical_days:
        return 100.0

    span = critical_days - optimal_days
    if span <= 0:
        return 100.0

    normalized = ((days - optimal_days) / float(span)) * 100.0
    return max(0.0, min(100.0, round(normalized, 2)))
