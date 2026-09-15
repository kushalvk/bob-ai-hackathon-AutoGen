"""Health check API router for verifying application boot and database connection."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.backend.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to confirm application status and DB connectivity.

    Args:
        db (Session): Database session injected via dependency.

    Returns:
        dict: Status payload confirming application and database operational state.

    Raises:
        HTTPException: 500 status code if database query fails.
    """
    try:
        # Execute test query to confirm DB connection
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "service": "ClinGuard AI Backend",
            "database": "connected",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}",
        )
