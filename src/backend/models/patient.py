"""Patient SQLAlchemy data model representing trial participants."""

from sqlalchemy import Column, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from src.backend.database import Base


class Patient(Base):
    """Clinical Trial Patient entity.

    Represents a subject enrolled at a specific site.

    Attributes:
        patient_id (str): Primary key unique identifier (e.g. 'PAT-101-001').
        site_id (str): Foreign key referencing Site.
        enrollment_date (date): Date patient was enrolled in trial.
    """
    __tablename__ = "patients"

    patient_id = Column(String(64), primary_key=True, index=True)
    site_id = Column(String(64), ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_date = Column(Date, nullable=False)

    # Relationships
    site = relationship("Site", back_populates="patients")
    visit_records = relationship("VisitRecord", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Patient(id='{self.patient_id}', site_id='{self.site_id}')>"
