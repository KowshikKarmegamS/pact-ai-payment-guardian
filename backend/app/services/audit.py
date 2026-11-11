"""Audit logging service for tracking security, policy evaluations, and payment events."""

import re
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import AuditLog

# A key is redacted when one of its word segments matches, or when it contains
# one of the substrings below. Segment matching avoids false positives such as
# "shipping" matching "pin".
_SENSITIVE_SEGMENTS = {"password", "secret", "token", "authorization", "cvv", "pin", "ssn", "credential", "cookie"}
_SENSITIVE_SUBSTRINGS = ("api_key", "apikey", "client_secret", "access_token", "card_number", "cardnumber", "bearer")
REDACTED = "***REDACTED***"
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")


def _is_sensitive(key: str) -> bool:
    k = str(key).lower()
    if any(s in k for s in _SENSITIVE_SUBSTRINGS):
        return True
    return any(seg in _SENSITIVE_SEGMENTS for seg in re.split(r"[^a-z0-9]+", k) if seg)


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return _BEARER_RE.sub("Bearer " + REDACTED, value)
    return value


def sanitize_audit_details(data: Any) -> Any:
    """Recursively scrub sensitive keys and bearer tokens from audit payloads."""
    if isinstance(data, list):
        return [sanitize_audit_details(item) for item in data]
    if not isinstance(data, dict):
        return _scrub_value(data)

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive(key):
            cleaned[key] = REDACTED
        else:
            cleaned[key] = sanitize_audit_details(value)
    return cleaned


def log_audit_event(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any],
    commit: bool = True,
) -> AuditLog:
    """Record a sanitized audit log event."""
    audit_entry = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=sanitize_audit_details(details),
    )
    db.add(audit_entry)
    if commit:
        db.commit()
        db.refresh(audit_entry)
    return audit_entry
