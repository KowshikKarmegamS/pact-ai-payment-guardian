"""Health check and non-sensitive system status."""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.config import get_settings
from app.paypal import PayPalError, describe_sandbox_status, get_access_token

router = APIRouter(tags=["Health"])

_oauth_cache: Dict[str, Any] = {"checked_at": 0.0, "result": None}
_OAUTH_TTL = 120.0


@router.get("/health")
def get_health() -> Dict[str, str]:
    return {
        "status": "healthy",
        "version": "1.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status", summary="AI provider and PayPal Sandbox configuration status (no secrets)")
async def get_status(check_paypal: bool = Query(False, description="Perform a live Sandbox OAuth check")) -> Dict[str, Any]:
    s = get_settings()
    paypal = describe_sandbox_status()
    oauth: Dict[str, Any] = {"checked": False}

    if check_paypal:
        now = time.time()
        if _oauth_cache["result"] is not None and now - _oauth_cache["checked_at"] < _OAUTH_TTL:
            oauth = _oauth_cache["result"]
        else:
            try:
                await get_access_token()
                oauth = {"checked": True, "ok": True}
            except PayPalError as err:
                oauth = {"checked": True, "ok": False, "code": err.code, "message": err.message}
            _oauth_cache.update(checked_at=now, result=oauth)
    paypal["oauth"] = oauth

    return {
        "ai": {
            "mode": s.ai_provider,
            "model": s.ai_model,
            "gemini_key_configured": s.gemini_configured,
            "api_key_configured": s.ai_provider != "heuristic",
            "note": s.ai_missing_key_note,
        },
        "paypal": paypal,
        "policy_engine": {"mode": "deterministic", "authority": "sole authorization authority"},
        "currency": s.currency,
    }
