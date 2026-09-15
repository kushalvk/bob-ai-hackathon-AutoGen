"""ClinGuard AI FastAPI Backend Application Entrypoint."""

from fastapi import FastAPI
from src.backend.config import settings
from src.backend.api.health import router as health_router
from src.backend.api.detect import router as detect_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="ClinGuard AI Clinical Protocol Compliance & Deviation Detection Platform Backend",
    version="1.0.0",
)

# Include API routers
app.include_router(health_router)
app.include_router(detect_router)


@app.get("/")
def root():
    """Root endpoint redirecting/informing about API health and documentation.

    Returns:
        dict: Welcome message with link to health check and docs.
    """
    return {
        "message": "Welcome to ClinGuard AI Backend API",
        "health_check": "/health",
        "detect_run": "/api/detect/run",
        "detect_results": "/api/detect/results",
        "docs": "/docs",
    }
