"""FastAPI application entrypoint for PACT – AI Payment Guardian."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import seed_catalog, seed_mandates
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import audit, health, mandates, payments, products, proposals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pact.app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if not settings.paypal_is_sandbox:
        logger.error("PAYPAL_BASE_URL is not a PayPal Sandbox endpoint; PayPal calls will be refused.")
    init_db()
    db = SessionLocal()
    try:
        seed_catalog(db)
        seed_mandates(db)
    finally:
        db.close()
    logger.info(
        "PACT started: AI=%s, PayPal=%s (%s), currency=%s, app_base_url=%s",
        f"{settings.ai_provider}:{settings.ai_model}" if settings.ai_model else "heuristic-fallback",
        "sandbox" if settings.paypal_is_sandbox else "INVALID",
        "credentials set" if settings.paypal_credentials_configured else "credentials missing",
        settings.currency,
        settings.app_base_url,
    )
    yield


app = FastAPI(
    title="PACT – AI Payment Guardian API",
    description=(
        "AI recommends → deterministic code authorizes → human approves → PayPal executes. "
        "Spending mandates, a deterministic policy engine, fingerprint-bound human approval "
        "and verified PayPal Sandbox capture."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Accept"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
        errors.append({"field": loc, "message": e.get("msg")})
    message = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": {"code": "VALIDATION_ERROR", "message": message, "errors": errors}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": "An internal server error occurred."}},
    )


for r in (health, products, mandates, proposals, payments, audit):
    app.include_router(r.router, prefix="/api")


# ---------------------------------------------------------------------------
# Serve the built React app (single-service deployment). /api and /docs win.
# ---------------------------------------------------------------------------
_dist = Path(settings.FRONTEND_DIST)
if not _dist.is_absolute():
    _dist = (Path(__file__).resolve().parent.parent / _dist).resolve()
_index = _dist / "index.html"

if _index.exists():
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "API route not found."})
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and _dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_index)
else:
    @app.get("/", tags=["Root"])
    def read_root() -> dict:
        return {"service": "PACT – AI Payment Guardian", "status": "operational", "docs_url": "/docs", "api_prefix": "/api",
                "frontend": "not built (run `npm run build` in frontend/)"}
