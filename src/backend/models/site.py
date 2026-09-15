"""Site SQLAlchemy data model representing clinical trial investigation sites."""

from sqlalchemy import Column, String, Integer, Float, Date
from sqlalchemy.orm import relationship
from src.backend.database import Base


class Site(Base):
    """Clinical Trial Site entity.

    Represents an investigator site conducting trial activities.

    Attributes:
        site_id (str): Primary key unique identifier (e.g. 'SITE-101').
        name (str): Hospital/clinic name.
        country (str): Country location.
        enrollment_target (int): Target number of patients to enroll.
        staff_turnover_rate (float): Annual site staff turnover rate (0.0 - 1.0).
        last_monitoring_visit_date (date): Date of the most recent CRA monitoring visit.
    """
    __tablename__ = "sites"

    site_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    enrollment_target = Column(Integer, nullable=False, default=0)
    staff_turnover_rate = Column(Float, nullable=False, default=0.0)
    last_monitoring_visit_date = Column(Date, nullable=True)

    # Relationships
    patients = relationship("Patient", back_populates="site", cascade="all, delete-orphan")
    deviations = relationship("Deviation", back_populates="site", cascade="all, delete-orphan")
    risk_scores = relationship("SiteRiskScore", back_populates="site", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Site(id='{self.site_id}', name='{self.name}', country='{self.country}')>"
