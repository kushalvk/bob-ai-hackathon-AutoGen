"""Protocol SQLAlchemy data model representing clinical trial protocol specifications."""

from sqlalchemy import Column, String, JSON
from src.backend.database import Base


class Protocol(Base):
    """Clinical Trial Protocol entity.

    Contains trial design specs, visit windows, dosing instructions,
    prohibited medications, and patient eligibility criteria.

    Attributes:
        protocol_id (str): Primary key unique identifier (e.g. 'PROTO-001').
        title (str): Official study title.
        version (str): Protocol version string (e.g. '1.0').
        visit_schedule (list[dict]): Expected visit timeline specs
            [{'visit_name': str, 'day_offset': int, 'window_days': int}].
        dosing_schedule (list[dict]): Per-visit drug dosing specifications
            [{'visit_name': str, 'drug': str, 'dose': float, 'unit': str}].
        prohibited_medications (list[str]): List of banned drug names.
        eligibility_criteria (list[str]): List of protocol inclusion/exclusion criteria.
    """
    __tablename__ = "protocols"

    protocol_id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    version = Column(String(32), nullable=False, default="1.0")
    visit_schedule = Column(JSON, nullable=False, default=list)
    dosing_schedule = Column(JSON, nullable=False, default=list)
    prohibited_medications = Column(JSON, nullable=False, default=list)
    eligibility_criteria = Column(JSON, nullable=False, default=list)

    def __repr__(self) -> str:
        return f"<Protocol(id='{self.protocol_id}', title='{self.title}', version='{self.version}')>"
