"""ClinGuard AI FastAPI Backend Application Entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.config import settings
from src.backend.api.health import router as health_router
from src.backend.api.detect import router as detect_router
from src.backend.api.risk import router as risk_router
from src.backend.api.capa import router as capa_router
from src.backend.api.chat import router as chat_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="ClinGuard AI Clinical Protocol Compliance & Deviation Detection Platform Backend",
    version="1.0.0",
)

# Configure CORS for frontend development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health_router)
app.include_router(detect_router)
app.include_router(risk_router)
app.include_router(capa_router)
app.include_router(chat_router)


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
        "risk_compute": "/api/risk/compute",
        "risk_scores": "/api/risk/scores",
        "docs": "/docs",
    }