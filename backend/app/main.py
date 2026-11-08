"""FastAPI application entrypoint for PACT – AI Payment Guardian."""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.catalog import seed_catalog, seed_mandates
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import audit, health, mandates, payments, products, proposals

logger = logging.getLogger("pact.app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to initialize database and seed catalog data on startup."""
    # 1. Initialize DB tables
    init_db()

    # 2. Seed product catalog and initial mandates if empty
    db = SessionLocal()
    try:
        seed_catalog(db)
        seed_mandates(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="PACT – AI Payment Guardian API",
    description=(
        "Autonomous Agent Payment Boundary Protection Platform. "
        "Enforces deterministic policy evaluation, spending mandates, and human-in-the-loop approvals."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# CORS Configuration
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Exception Handlers
# -----------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Provide structured validation error messages without leaking internal tracebacks."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format HTTP exceptions into standard error payloads."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Intercept unhandled exceptions and prevent leaking internal stack traces or secrets."""
    logger.error("Unhandled internal server error: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# -----------------------------------------------------------------------------
# Router Registrations
app.include_router(health.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(mandates.router, prefix="/api")
app.include_router(proposals.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


@app.get("/", tags=["Root"])
def read_root() -> dict:
    """Root endpoint welcoming API consumers and linking to documentation."""
    return {
        "service": "PACT – AI Payment Guardian",
        "status": "operational",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }
