"""Add evidence column to deviations table.

Revision ID: 002_add_evidence_to_deviation
Revises: 001_initial_schema
Create Date: 2026-09-15 15:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_evidence_to_deviation"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deviations", sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("deviations", "evidence")
