"""Health check and service status router."""

from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", response_model=Dict[str, str], tags=["Health"])
def get_health() -> Dict[str, str]:
    """Return health status, current version, and UTC timestamp."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
