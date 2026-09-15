"""VisitRecord SQLAlchemy data model representing trial patient visits."""

from sqlalchemy import Column, String, Date, Float, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from src.backend.database import Base


class VisitRecord(Base):
    """Visit Record entity.

    Tracks a scheduled and actual subject study visit, including dosing,
    concomitant medications, and clinical notes.

    Attributes:
        record_id (str): Primary key unique identifier (e.g. 'REC-0001').
        patient_id (str): Foreign key referencing Patient.
        visit_name (str): Protocol visit milestone (e.g. 'Screening', 'Week 4').
        scheduled_date (date): Target scheduled visit date.
        actual_date (date, optional): Actual date visit occurred (None if missed).
        dose_given (float, optional): Administered study drug dose.
        drug (str, optional): Administered study drug name.
        concomitant_meds (list[str]): List of active concomitant medications reported during visit.
        notes (str, optional): Clinical study coordinator comments / logs.
    """
    __tablename__ = "visit_records"

    record_id = Column(String(64), primary_key=True, index=True)
    patient_id = Column(String(64), ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    visit_name = Column(String(100), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    actual_date = Column(Date, nullable=True)
    dose_given = Column(Float, nullable=True)
    drug = Column(String(100), nullable=True)
    concomitant_meds = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="visit_records")
    deviations = relationship("Deviation", back_populates="visit_record", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VisitRecord(id='{self.record_id}', patient='{self.patient_id}', visit='{self.visit_name}')>"
