"""Deviation SQLAlchemy data model representing protocol deviations."""

from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from src.backend.database import Base


class Deviation(Base):
    """Protocol Deviation entity.

    Tracks detected clinical trial protocol deviations across sites and patients.
    Supports hybrid severity classification with both rule-based and LLM-reviewed
    severity values for full audit trail transparency.

    Attributes:
        deviation_id (str): Primary key unique identifier (e.g. 'DEV-0001').
        record_id (str, optional): Foreign key referencing VisitRecord (if record-specific).
        site_id (str): Foreign key referencing Site where deviation occurred.
        type (str): Deviation classification category
            ('missed_visit', 'wrong_dose', 'banned_comed', 'eligibility_breach', 'documentation').
        severity (str): Backward-compatible severity grade — always equals final_severity.
        default_severity (str): Rule-table severity from deterministic classification.
        final_severity (str): Post-LLM-review severity (equals default_severity if no override).
        severity_rationale (str): Clinical rationale explaining assigned severity level.
            Contains LLM rationale citing ICH E6(R2) if LLM-reviewed.
        severity_source (str): Origin of the final severity: 'deterministic' or 'llm_override'.
        evidence (dict): Structured audit trail details ({field, expected, actual, delta/details}).
        detected_at (datetime): Timestamp when deviation was identified or flagged.
    """
    __tablename__ = "deviations"

    deviation_id = Column(String(64), primary_key=True, index=True)
    record_id = Column(String(64), ForeignKey("visit_records.record_id", ondelete="CASCADE"), nullable=True, index=True)
    site_id = Column(String(64), ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False)
    default_severity = Column(String(50), nullable=False, server_default="minor")
    final_severity = Column(String(50), nullable=False, server_default="minor")
    severity_rationale = Column(Text, nullable=False)
    severity_source = Column(String(50), nullable=False, server_default="deterministic")
    evidence = Column(JSON, nullable=False, default=dict)
    detected_at = Column(DateTime, nullable=False)

    # Relationships
    site = relationship("Site", back_populates="deviations")
    visit_record = relationship("VisitRecord", back_populates="deviations")

    def __repr__(self) -> str:
        return (
            f"<Deviation(id='{self.deviation_id}', site='{self.site_id}', "
            f"type='{self.type}', default='{self.default_severity}', "
            f"final='{self.final_severity}', source='{self.severity_source}')>"
        )
