"""CAPAReport SQLAlchemy data model representing Corrective and Preventive Action plans."""

from sqlalchemy import Column, String, Text, Date, JSON


from src.backend.database import Base


class CAPAReport(Base):
    """Corrective and Preventive Action (CAPA) Report entity.

    Tracks root cause analysis and resolution workflows for major/repeated protocol deviations.

    Attributes:
        capa_id (str): Primary key unique identifier (e.g. 'CAPA-101-001').
        deviation_ids (list[str]): List of associated deviation primary key IDs.
        finding (str): Deterministic summary of the deviation(s) that triggered this CAPA.
        severity (str): Highest severity level from the constituent deviations
            ('major', 'minor', 'administrative').
        severity_rationale (str): Rationale for the assigned severity, pulled from
            the highest-severity Deviation record.
        root_cause (str): LLM-drafted narrative analysis of underlying failure root cause.
        corrective_action (str): LLM-drafted action taken to address immediate deviation.
        preventive_action (str): LLM-drafted long-term process changes to prevent recurrence.
        owner (str): Responsible quality monitor / CRA staff member.
        due_date (date): Target completion due date for CAPA execution.
        status (str): Current CAPA lifecycle status ('open', 'in_progress', 'pending_review', 'closed').
    """
    __tablename__ = "capa_reports"

    capa_id = Column(String(64), primary_key=True, index=True)
    deviation_ids = Column(JSON, nullable=False, default=list)
    finding = Column(Text, nullable=False, default="")
    severity = Column(String(50), nullable=False, default="minor")
    severity_rationale = Column(Text, nullable=False, default="")
    root_cause = Column(Text, nullable=False)
    corrective_action = Column(Text, nullable=False)
    preventive_action = Column(Text, nullable=False)
    owner = Column(String(100), nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(50), nullable=False, default="open")

    def __repr__(self) -> str:
        """Return string representation of the CAPAReport instance."""
        return (
            f"<CAPAReport(id='{self.capa_id}', severity='{self.severity}', "
            f"owner='{self.owner}', status='{self.status}')>"
        )
