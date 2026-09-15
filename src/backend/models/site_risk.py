"""SiteRiskScore SQLAlchemy data model representing site risk score assessments."""

from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from src.backend.database import Base


class SiteRiskScore(Base):
    """Site Risk Score entity.

    Stores calculated composite risk scores and breakdown of contributing risk factors
    for trial sites.

    Attributes:
        score_id (str): Primary key unique identifier (e.g. 'RISK-101-20260915').
        site_id (str): Foreign key referencing Site.
        score (float): Calculated risk score ranging from 0.0 (lowest risk) to 100.0 (highest risk).
        computed_at (datetime): Timestamp when score was calculated.
        contributing_factors (list[dict]): Detailed factor weights and values
            [{'factor': str, 'weight': float, 'value': float}].
    """
    __tablename__ = "site_risk_scores"

    score_id = Column(String(64), primary_key=True, index=True)
    site_id = Column(String(64), ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    computed_at = Column(DateTime, nullable=False)
    contributing_factors = Column(JSON, nullable=False, default=list)

    # Relationships
    site = relationship("Site", back_populates="risk_scores")

    def __repr__(self) -> str:
        return f"<SiteRiskScore(id='{self.score_id}', site='{self.site_id}', score={self.score})>"
