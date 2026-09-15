"""CAPA export utilities — Markdown and PDF rendering.

Provides functions to export a CAPAReport instance to structured
Markdown text or a PDF document (using fpdf2).
"""

import logging
from typing import Any

from fpdf import FPDF

logger = logging.getLogger(__name__)


def _get_attr(obj: Any, key: str, default: str = "") -> str:
    """Safely extract a string attribute from an ORM instance or dict.

    Args:
        obj: CAPAReport ORM instance or dictionary.
        key: Attribute/key name.
        default: Fallback value.

    Returns:
        String value of the attribute.
    """
    if isinstance(obj, dict):
        val = obj.get(key, default)
    else:
        val = getattr(obj, key, default)
    return str(val) if val is not None else default


def export_capa_markdown(capa: Any) -> str:
    """Render a CAPAReport as a structured Markdown document.

    Sections: Finding, Severity, Root Cause, Corrective Action,
    Preventive Action, Owner, Due Date, Status.

    Args:
        capa: CAPAReport ORM instance or dictionary with CAPA fields.

    Returns:
        Complete Markdown string ready for display or file export.
    """
    capa_id = _get_attr(capa, "capa_id")
    deviation_ids = _get_attr(capa, "deviation_ids", "[]")
    finding = _get_attr(capa, "finding")
    severity = _get_attr(capa, "severity")
    severity_rationale = _get_attr(capa, "severity_rationale")
    root_cause = _get_attr(capa, "root_cause")
    corrective_action = _get_attr(capa, "corrective_action")
    preventive_action = _get_attr(capa, "preventive_action")
    owner = _get_attr(capa, "owner")
    due_date = _get_attr(capa, "due_date")
    status = _get_attr(capa, "status")

    md = f"""# CAPA Report: {capa_id}

## Finding

{finding}

**Related Deviation IDs:** {deviation_ids}

## Severity

**Level:** {severity}

**Rationale:** {severity_rationale}

## Root Cause Analysis

{root_cause}

## Corrective Action

{corrective_action}

## Preventive Action

{preventive_action}

## Assignment

| Field    | Value        |
|----------|--------------|
| Owner    | {owner}      |
| Due Date | {due_date}   |
| Status   | {status}     |
"""
    return md


def export_capa_pdf(capa: Any) -> bytes:
    """Generate a PDF document from a CAPAReport.

    Uses fpdf2 (FPDF) for lightweight, pure-Python PDF generation
    with no system-level dependencies.

    Args:
        capa: CAPAReport ORM instance or dictionary with CAPA fields.

    Returns:
        PDF file contents as bytes.
    """
    capa_id = _get_attr(capa, "capa_id")
    deviation_ids = _get_attr(capa, "deviation_ids", "[]")
    finding = _get_attr(capa, "finding")
    severity = _get_attr(capa, "severity")
    severity_rationale = _get_attr(capa, "severity_rationale")
    root_cause = _get_attr(capa, "root_cause")
    corrective_action = _get_attr(capa, "corrective_action")
    preventive_action = _get_attr(capa, "preventive_action")
    owner = _get_attr(capa, "owner")
    due_date = _get_attr(capa, "due_date")
    status = _get_attr(capa, "status")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"CAPA Report: {capa_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    def _section(title: str, body: str) -> None:
        """Add a section heading and body text to the PDF.

        Args:
            title: Section heading text.
            body: Section body text.
        """
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        # Replace special characters that Latin-1 cannot encode
        safe_body = body.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_body)
        pdf.ln(3)

    _section("Finding", finding)
    _section("Related Deviation IDs", str(deviation_ids))
    _section("Severity", f"{severity} — {severity_rationale}")
    _section("Root Cause Analysis", root_cause)
    _section("Corrective Action", corrective_action)
    _section("Preventive Action", preventive_action)

    # Assignment table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Assignment", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    col_w = 45
    val_w = 140
    for label, value in [("Owner", owner), ("Due Date", due_date), ("Status", status)]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(col_w, 7, label, border=1)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(val_w, 7, value, border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
