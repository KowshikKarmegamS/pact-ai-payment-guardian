"""Agent Gateway credentials.

Each external AI agent gets its own key, shown once when it is registered. Only the SHA-256
hash is stored (the key is 192 random bits, so a plain hash is sufficient), and the key is
never logged or written to the audit trail. Revoking an agent stops its key immediately.
"""

import hashlib
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentClient, utc_now

KEY_PREFIX = "pact_agent_"


def new_agent_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(24)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def display_prefix(key: str) -> str:
    return key[: len(KEY_PREFIX) + 4] + "…"


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "AGENT_UNAUTHORIZED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_agent(
    authorization: Optional[str] = Header(default=None),
    x_pact_agent_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentClient:
    """Authenticate the calling agent from `Authorization: Bearer <key>` or `X-PACT-Agent-Key`."""
    key = None
    if authorization and authorization.lower().startswith("bearer "):
        key = authorization[7:].strip()
    elif x_pact_agent_key:
        key = x_pact_agent_key.strip()
    if not key or not key.startswith(KEY_PREFIX):
        raise _unauthorized("Send your PACT agent key as 'Authorization: Bearer pact_agent_…'.")
    agent = db.query(AgentClient).filter(AgentClient.key_hash == hash_key(key)).first()
    if agent is None:
        raise _unauthorized("Unknown agent key.")
    if agent.revoked_at is not None:
        raise _unauthorized("This agent's access was revoked in the PACT Control Center.")
    agent.last_used_at = utc_now()
    db.commit()
    return agent
