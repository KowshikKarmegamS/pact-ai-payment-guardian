"""FastAPI application entrypoint for PACT – AI Payment Authorization Gateway."""

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
from app.routers import agents, audit, gateway, health, mandates, owner, payments, products, proposals
from app.services import owner_auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pact.app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if not settings.paypal_is_sandbox:
        logger.error("PAYPAL_BASE_URL is not a PayPal Sandbox endpoint; PayPal calls will be refused.")
    if owner_auth.misconfigured():
        logger.error("REQUIRE_OWNER_AUTH is on but OWNER_PASSWORD is not set: owner routes are refused until it is.")
    elif not owner_auth.auth_enabled():
        logger.warning("OWNER_PASSWORD is not set: the Control Center is open to anyone who can reach it (local demo mode).")
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
    title="PACT – AI Payment Authorization Gateway",
    description=(
        "The authorization gateway for AI-powered commerce. Any AI agent (Claude, ChatGPT, custom) asks PACT "
        "for spending authority through the Agent Gateway (`/api/agent/v1`, or the MCP server in "
        "`integrations/mcp`). A deterministic policy engine decides, a human approves the exact purchase, "
        "and PayPal executes. Agents can request purchases but can never approve or capture a payment."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Accept"],
)


@app.middleware("http")
async def require_owner(request: Request, call_next):
    """Owner-facing /api routes need the owner session when owner auth is on (or required)."""
    if request.method != "OPTIONS" and owner_auth.needs_owner(request.url.path):
        if owner_auth.misconfigured():
            return JSONResponse(status_code=503, content={"detail": {
                "code": "OWNER_AUTH_NOT_CONFIGURED",
                "message": "Owner sign-in is required on this deployment but OWNER_PASSWORD is not set."}})
        if owner_auth.auth_enabled() and not owner_auth.token_valid(request.cookies.get(owner_auth.COOKIE_NAME)):
            return JSONResponse(status_code=401, content={"detail": {
                "code": "OWNER_AUTH_REQUIRED", "message": "Sign in to the PACT Control Center to continue."}})
    return await call_next(request)


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


for r in (health, owner, products, mandates, proposals, payments, audit, agents, gateway):
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
        return {"service": "PACT – AI Payment Authorization Gateway", "status": "operational", "docs_url": "/docs", "api_prefix": "/api",
                "frontend": "not built (run `npm run build` in frontend/)"}
