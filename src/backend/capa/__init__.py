"""CAPA (Corrective and Preventive Action) report generation package.

Provides deviation clustering, LLM-assisted narrative generation,
and export to Markdown/PDF formats.
"""

from src.backend.capa.generator import (
    cluster_deviations,
    generate_capa_report,
    generate_capa_reports_for_site,
)
from src.backend.capa.export import export_capa_markdown, export_capa_pdf

__all__ = [
    "cluster_deviations",
    "generate_capa_report",
    "generate_capa_reports_for_site",
    "export_capa_markdown",
    "export_capa_pdf",
]
