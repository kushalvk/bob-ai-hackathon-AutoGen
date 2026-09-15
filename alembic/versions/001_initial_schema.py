"""Initial schema creation for ClinGuard AI entities.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-15 15:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Protocols table
    op.create_table(
        "protocols",
        sa.Column("protocol_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("visit_schedule", sa.JSON(), nullable=False),
        sa.Column("dosing_schedule", sa.JSON(), nullable=False),
        sa.Column("prohibited_medications", sa.JSON(), nullable=False),
        sa.Column("eligibility_criteria", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("protocol_id"),
    )
    op.create_index(op.f("ix_protocols_protocol_id"), "protocols", ["protocol_id"], unique=False)

    # Sites table
    op.create_table(
        "sites",
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("enrollment_target", sa.Integer(), nullable=False),
        sa.Column("staff_turnover_rate", sa.Float(), nullable=False),
        sa.Column("last_monitoring_visit_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("site_id"),
    )
    op.create_index(op.f("ix_sites_site_id"), "sites", ["site_id"], unique=False)

    # Patients table
    op.create_table(
        "patients",
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("enrollment_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("patient_id"),
    )
    op.create_index(op.f("ix_patients_patient_id"), "patients", ["patient_id"], unique=False)
    op.create_index(op.f("ix_patients_site_id"), "patients", ["site_id"], unique=False)

    # Visit Records table
    op.create_table(
        "visit_records",
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("visit_name", sa.String(length=100), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("dose_given", sa.Float(), nullable=True),
        sa.Column("drug", sa.String(length=100), nullable=True),
        sa.Column("concomitant_meds", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index(op.f("ix_visit_records_patient_id"), "visit_records", ["patient_id"], unique=False)
    op.create_index(op.f("ix_visit_records_record_id"), "visit_records", ["record_id"], unique=False)

    # Deviations table
    op.create_table(
        "deviations",
        sa.Column("deviation_id", sa.String(length=64), nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=True),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("severity_rationale", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["visit_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("deviation_id"),
    )
    op.create_index(op.f("ix_deviations_deviation_id"), "deviations", ["deviation_id"], unique=False)
    op.create_index(op.f("ix_deviations_record_id"), "deviations", ["record_id"], unique=False)
    op.create_index(op.f("ix_deviations_site_id"), "deviations", ["site_id"], unique=False)

    # Site Risk Scores table
    op.create_table(
        "site_risk_scores",
        sa.Column("score_id", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("contributing_factors", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.site_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("score_id"),
    )
    op.create_index(op.f("ix_site_risk_scores_score_id"), "site_risk_scores", ["score_id"], unique=False)
    op.create_index(op.f("ix_site_risk_scores_site_id"), "site_risk_scores", ["site_id"], unique=False)

    # CAPA Reports table
    op.create_table(
        "capa_reports",
        sa.Column("capa_id", sa.String(length=64), nullable=False),
        sa.Column("deviation_ids", sa.JSON(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("corrective_action", sa.Text(), nullable=False),
        sa.Column("preventive_action", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("capa_id"),
    )
    op.create_index(op.f("ix_capa_reports_capa_id"), "capa_reports", ["capa_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_capa_reports_capa_id"), table_name="capa_reports")
    op.drop_table("capa_reports")
    op.drop_index(op.f("ix_site_risk_scores_site_id"), table_name="site_risk_scores")
    op.drop_index(op.f("ix_site_risk_scores_score_id"), table_name="site_risk_scores")
    op.drop_table("site_risk_scores")
    op.drop_index(op.f("ix_deviations_site_id"), table_name="deviations")
    op.drop_index(op.f("ix_deviations_record_id"), table_name="deviations")
    op.drop_index(op.f("ix_deviations_deviation_id"), table_name="deviations")
    op.drop_table("deviations")
    op.drop_index(op.f("ix_visit_records_record_id"), table_name="visit_records")
    op.drop_index(op.f("ix_visit_records_patient_id"), table_name="visit_records")
    op.drop_table("visit_records")
    op.drop_index(op.f("ix_patients_site_id"), table_name="patients")
    op.drop_index(op.f("ix_patients_patient_id"), table_name="patients")
    op.drop_table("patients")
    op.drop_index(op.f("ix_sites_site_id"), table_name="sites")
    op.drop_table("sites")
    op.drop_index(op.f("ix_protocols_protocol_id"), table_name="protocols")
    op.drop_table("protocols")
