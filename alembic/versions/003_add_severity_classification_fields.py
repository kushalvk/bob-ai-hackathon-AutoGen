"""Add severity classification fields to deviations table.

Revision ID: 003_add_severity_classification_fields
Revises: 002_add_evidence_to_deviation
Create Date: 2026-09-15 16:10:00.000000

Adds columns for hybrid severity classification:
- default_severity: Rule-table deterministic severity
- final_severity: Post-LLM-review severity
- severity_source: 'deterministic' or 'llm_override'
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_add_severity_classification_fields"
down_revision: Union[str, None] = "002_add_evidence_to_deviation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add severity classification columns and backfill existing rows."""
    op.add_column(
        "deviations",
        sa.Column("default_severity", sa.String(50), nullable=False, server_default="minor"),
    )
    op.add_column(
        "deviations",
        sa.Column("final_severity", sa.String(50), nullable=False, server_default="minor"),
    )
    op.add_column(
        "deviations",
        sa.Column("severity_source", sa.String(50), nullable=False, server_default="deterministic"),
    )

    # Backfill: set default_severity and final_severity to existing severity value
    op.execute("UPDATE deviations SET default_severity = severity, final_severity = severity")


def downgrade() -> None:
    """Remove severity classification columns."""
    op.drop_column("deviations", "severity_source")
    op.drop_column("deviations", "final_severity")
    op.drop_column("deviations", "default_severity")
