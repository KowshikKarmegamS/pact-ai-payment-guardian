"""Owner (Control Center) authentication.

A deliberately small, dependency-free scheme for a single owner:
  * POST /api/owner/login with OWNER_PASSWORD sets an HttpOnly, SameSite=Lax session cookie
    holding "<expiry>.<HMAC-SHA256(expiry)>". No server-side session store is needed.
  * Middleware requires that cookie on every owner-facing /api route.
  * AI agents never use this: they authenticate to /api/agent/v1 with their own scoped keys.

SameSite=Lax keeps the cookie off cross-site POSTs (CSRF), HttpOnly keeps it away from page scripts.
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional

from app.config import get_settings

COOKIE_NAME = "pact_owner"
DEFAULT_SECRET = "change-this-to-a-random-secret"

# Paths that never need the owner session.
_OPEN_PREFIXES = ("/api/agent/", "/api/owner/")
_OPEN_PATHS = {"/api/health", "/api/status"}

# If APP_SECRET_KEY was never changed, sign with a per-process random key instead (sessions then end on restart).
_PROCESS_SECRET = secrets.token_bytes(32)


def _key() -> bytes:
    s = get_settings()
    base = s.APP_SECRET_KEY.encode() if s.APP_SECRET_KEY and s.APP_SECRET_KEY != DEFAULT_SECRET else _PROCESS_SECRET
    # Binding the password into the key means changing OWNER_PASSWORD signs everyone out.
    return hashlib.sha256(base + b"|" + s.OWNER_PASSWORD.encode()).digest()


def auth_enabled() -> bool:
    return bool(get_settings().OWNER_PASSWORD)


def misconfigured() -> bool:
    s = get_settings()
    return bool(s.REQUIRE_OWNER_AUTH) and not s.OWNER_PASSWORD


def password_ok(candidate: str) -> bool:
    expected = get_settings().OWNER_PASSWORD
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def issue_token(now: Optional[float] = None) -> str:
    expiry = int((time.time() if now is None else now) + get_settings().OWNER_SESSION_HOURS * 3600)
    sig = hmac.new(_key(), str(expiry).encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def token_valid(token: Optional[str], now: Optional[float] = None) -> bool:
    if not token or "." not in token:
        return False
    expiry, sig = token.split(".", 1)
    if not expiry.isdigit():
        return False
    good = hmac.new(_key(), expiry.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and int(expiry) > (time.time() if now is None else now)


def needs_owner(path: str) -> bool:
    if not path.startswith("/api/") and path != "/api":
        return False
    if path in _OPEN_PATHS or path.startswith(_OPEN_PREFIXES):
        return False
    return True


class LoginThrottle:
    """At most 5 failed logins per client per 5 minutes (in memory; single instance)."""

    WINDOW, LIMIT = 300.0, 5

    def __init__(self) -> None:
        self._fails: dict = {}

    def blocked(self, client: str) -> bool:
        now = time.time()
        recent = [t for t in self._fails.get(client, []) if now - t < self.WINDOW]
        self._fails[client] = recent
        return len(recent) >= self.LIMIT

    def fail(self, client: str) -> None:
        self._fails.setdefault(client, []).append(time.time())

    def reset(self, client: str) -> None:
        self._fails.pop(client, None)


throttle = LoginThrottle()
