"""CAPA report generator — clustering, finding assembly, and LLM narrative drafting.

Clustering Rule
===============
Deviations are grouped into a single CAPA report when they share ALL of:

1. **Same site_id** — deviations must originate from the same clinical site.
2. **Same type** — deviations must be the same category (e.g., all 'missed_visit').
3. **Within a 30-day rolling window** — the gap between the first and last
   deviation in the cluster must be ≤30 calendar days.

Clusters are formed greedily: deviations are sorted by ``detected_at``,
and a new cluster is started whenever a deviation's timestamp exceeds
30 days from the current cluster's first deviation.

A deviation belongs to exactly one cluster.

LLM Boundary
=============
Only three narrative fields are LLM-authored:
- ``root_cause``
- ``corrective_action``
- ``preventive_action``

All other CAPA fields (finding summary, severity, severity_rationale,
owner, due_date, status, deviation_ids) are assembled deterministically
from existing Deviation data or caller-supplied defaults.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.backend.llm_client import BaseLLMClient, _capa_narrative_fallback
from src.backend.models.capa import CAPAReport

logger = logging.getLogger(__name__)

# Clustering parameters
CLUSTER_WINDOW_DAYS = 30

# Severity ranking for picking the highest in a cluster
_SEVERITY_RANK = {"major": 3, "minor": 2, "administrative": 1}


def cluster_deviations(
    deviations: List[Any],
) -> List[List[Any]]:
    """Group deviations into clusters for CAPA generation.

    Clustering rule: same ``site_id`` + same ``type`` + detected within
    a 30-day rolling window. Deviations are sorted by ``detected_at``
    and grouped greedily — a new cluster starts when a deviation's
    timestamp exceeds 30 days from the cluster's first deviation.

    Args:
        deviations: List of Deviation ORM instances or dicts with
            ``site_id``, ``type``, and ``detected_at`` attributes/keys.

    Returns:
        List of clusters, where each cluster is a list of deviations
        that should be covered by a single CAPA report.
    """
    if not deviations:
        return []

    def _get_attr(dev: Any, key: str) -> Any:
        """Extract an attribute from a Deviation (ORM instance or dict)."""
        if isinstance(dev, dict):
            return dev.get(key)
        return getattr(dev, key, None)

    # Group by (site_id, type)
    groups: Dict[Tuple[str, str], List[Any]] = defaultdict(list)
    for dev in deviations:
        site = _get_attr(dev, "site_id") or ""
        dev_type = _get_attr(dev, "type") or ""
        groups[(site, dev_type)].append(dev)

    clusters: List[List[Any]] = []

    for _key, group in groups.items():
        # Sort by detected_at within each group
        group.sort(key=lambda d: _get_attr(d, "detected_at") or date.min)

        current_cluster: List[Any] = []
        cluster_start = None

        for dev in group:
            det_at = _get_attr(dev, "detected_at")
            # Normalise to date for comparison
            if hasattr(det_at, "date"):
                det_date = det_at.date()
            elif isinstance(det_at, date):
                det_date = det_at
            else:
                det_date = date.min

            if not current_cluster:
                current_cluster = [dev]
                cluster_start = det_date
            elif (det_date - cluster_start).days <= CLUSTER_WINDOW_DAYS:
                current_cluster.append(dev)
            else:
                clusters.append(current_cluster)
                current_cluster = [dev]
                cluster_start = det_date

        if current_cluster:
            clusters.append(current_cluster)

    return clusters


def _get_deviation_attr(dev: Any, key: str, default: Any = None) -> Any:
    """Safely extract an attribute from a Deviation ORM instance or dict.

    Args:
        dev: Deviation ORM instance or dictionary.
        key: Attribute/key name.
        default: Fallback value if key not found.

    Returns:
        The attribute value or the default.
    """
    if isinstance(dev, dict):
        return dev.get(key, default)
    return getattr(dev, key, default)


def _pick_highest_severity(
    cluster: List[Any],
) -> Tuple[str, str]:
    """Select the highest severity and its rationale from a cluster.

    Severity ranking: major > minor > administrative.
    If multiple deviations share the highest rank, the rationale from the
    first one (by detection order) is used.

    Args:
        cluster: List of Deviation ORM instances or dicts.

    Returns:
        Tuple of (severity, severity_rationale).
    """
    best_severity = "administrative"
    best_rationale = ""
    best_rank = 0

    for dev in cluster:
        sev = (_get_deviation_attr(dev, "final_severity")
               or _get_deviation_attr(dev, "severity")
               or "administrative")
        rank = _SEVERITY_RANK.get(sev.lower(), 0)
        if rank > best_rank:
            best_rank = rank
            best_severity = sev.lower()
            best_rationale = (
                _get_deviation_attr(dev, "severity_rationale") or ""
            )

    return best_severity, best_rationale


def _build_finding_summary(cluster: List[Any]) -> str:
    """Build a deterministic finding summary from a deviation cluster.

    Produces text like:
    "3 deviation(s) of type 'missed_visit' at site SITE-101 between
     2026-08-01 and 2026-08-25. Highest severity: major."

    Args:
        cluster: Non-empty list of Deviation ORM instances or dicts.

    Returns:
        Human-readable finding summary string.
    """
    count = len(cluster)
    dev_type = _get_deviation_attr(cluster[0], "type") or "unknown"
    site_id = _get_deviation_attr(cluster[0], "site_id") or "unknown"

    dates = []
    for dev in cluster:
        det_at = _get_deviation_attr(dev, "detected_at")
        if det_at:
            if hasattr(det_at, "date"):
                dates.append(det_at.date())
            elif isinstance(det_at, date):
                dates.append(det_at)

    severity, _ = _pick_highest_severity(cluster)

    if dates:
        date_range = f"between {min(dates).isoformat()} and {max(dates).isoformat()}"
    else:
        date_range = "with unknown detection dates"

    noun = "deviation" if count == 1 else "deviations"
    return (
        f"{count} {noun} of type '{dev_type}' at site {site_id} "
        f"{date_range}. Highest severity: {severity}."
    )


def _build_deviation_summaries(cluster: List[Any]) -> List[Dict[str, Any]]:
    """Convert a cluster of deviations to summary dicts for the LLM prompt.

    Args:
        cluster: List of Deviation ORM instances or dicts.

    Returns:
        List of dictionaries with type, severity, severity_rationale, evidence.
    """
    summaries = []
    for dev in cluster:
        summaries.append({
            "type": _get_deviation_attr(dev, "type") or "unknown",
            "severity": (
                _get_deviation_attr(dev, "final_severity")
                or _get_deviation_attr(dev, "severity")
                or "unknown"
            ),
            "severity_rationale": (
                _get_deviation_attr(dev, "severity_rationale") or ""
            ),
            "evidence": _get_deviation_attr(dev, "evidence") or {},
        })
    return summaries


def generate_capa_report(
    cluster: List[Any],
    llm_client: Optional[BaseLLMClient] = None,
    owner: str = "Unassigned",
    due_date: Optional[date] = None,
    capa_id: Optional[str] = None,
) -> CAPAReport:
    """Generate a single CAPA report from a cluster of related deviations.

    Assembles all deterministic fields (finding, severity, deviation_ids,
    owner, due_date, status) from existing data, then calls the LLM client
    for the three narrative fields (root_cause, corrective_action,
    preventive_action). Falls back to canned narratives if no LLM is available.

    Args:
        cluster: Non-empty list of Deviation ORM instances or dicts.
        llm_client: Optional LLM client for narrative generation.
            If None, deterministic fallback narratives are used.
        owner: Responsible person for the CAPA. Defaults to 'Unassigned'.
        due_date: Target completion date. Defaults to 30 days from today.
        capa_id: Explicit CAPA ID. Auto-generated if not provided.

    Returns:
        A CAPAReport ORM instance (not yet persisted to DB).

    Raises:
        ValueError: If the cluster is empty.
    """
    if not cluster:
        raise ValueError("Cannot generate a CAPA report from an empty cluster.")

    # --- Deterministic fields ---
    deviation_ids = []
    for dev in cluster:
        dev_id = _get_deviation_attr(dev, "deviation_id")
        if dev_id:
            deviation_ids.append(dev_id)

    finding = _build_finding_summary(cluster)
    severity, severity_rationale = _pick_highest_severity(cluster)

    if due_date is None:
        due_date = date.today() + timedelta(days=30)

    if capa_id is None:
        site_id = _get_deviation_attr(cluster[0], "site_id") or "UNKNOWN"
        site_suffix = site_id.split("-")[1] if "-" in site_id else site_id
        capa_id = f"CAPA-{site_suffix}-001"

    # --- LLM-authored narrative fields ---
    deviation_summaries = _build_deviation_summaries(cluster)

    if llm_client is not None:
        try:
            narrative = llm_client.generate_capa_narrative(deviation_summaries)
        except Exception as e:
            logger.error(
                "LLM narrative generation failed: %s. Using fallback.", e
            )
            narrative = _capa_narrative_fallback(deviation_summaries)
    else:
        narrative = _capa_narrative_fallback(deviation_summaries)

    return CAPAReport(
        capa_id=capa_id,
        deviation_ids=deviation_ids,
        finding=finding,
        severity=severity,
        severity_rationale=severity_rationale,
        root_cause=narrative["root_cause"],
        corrective_action=narrative["corrective_action"],
        preventive_action=narrative["preventive_action"],
        owner=owner,
        due_date=due_date,
        status="open",
    )


def generate_capa_reports_for_site(
    deviations: List[Any],
    llm_client: Optional[BaseLLMClient] = None,
    owner: str = "Unassigned",
    due_date: Optional[date] = None,
) -> List[CAPAReport]:
    """Cluster deviations and generate one CAPA report per cluster.

    Convenience function that runs clustering, then generates a CAPA
    for each cluster with auto-incremented IDs.

    Args:
        deviations: List of Deviation ORM instances or dicts.
        llm_client: Optional LLM client for narrative generation.
        owner: Responsible person. Defaults to 'Unassigned'.
        due_date: Target completion date. Defaults to 30 days from today.

    Returns:
        List of CAPAReport instances (not yet persisted).
    """
    clusters = cluster_deviations(deviations)
    reports: List[CAPAReport] = []

    for idx, cluster in enumerate(clusters, start=1):
        site_id = _get_deviation_attr(cluster[0], "site_id") or "UNKNOWN"
        site_suffix = site_id.split("-")[1] if "-" in site_id else site_id
        capa_id = f"CAPA-{site_suffix}-{idx:03d}"

        report = generate_capa_report(
            cluster=cluster,
            llm_client=llm_client,
            owner=owner,
            due_date=due_date,
            capa_id=capa_id,
        )
        reports.append(report)

    return reports
