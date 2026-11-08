"""Audit logging service for tracking security, policy evaluations, and payment events."""

from typing import Any, Dict
from sqlalchemy.orm import Session
from app.models import AuditLog

# Keys that must be masked to prevent credential or sensitive data leakage
SENSITIVE_KEY_PATTERNS = {
    "password",
    "secret",
    "token",
    "authorization",
    "client_secret",
    "api_key",
    "card_number",
    "cvv",
    "pin",
}


def sanitize_audit_details(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively scrub sensitive keys and credentials from audit payloads."""
    if not isinstance(data, dict):
        return data

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEY_PATTERNS):
            cleaned[key] = "***REDACTED***"
        elif isinstance(value, dict):
            cleaned[key] = sanitize_audit_details(value)
        elif isinstance(value, list):
            cleaned[key] = [
                sanitize_audit_details(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    return cleaned


def log_audit_event(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any],
) -> AuditLog:
    """Record an immutable, sanitized audit log event.

    Args:
        db: Database session.
        event_type: High-level action identifier (e.g. MANDATE_CREATED, POLICY_CHECK).
        entity_type: Target entity model (e.g. Mandate, Proposal).
        entity_id: Target entity identifier.
        details: Contextual details (will be automatically sanitized).

    Returns:
        Persisted AuditLog instance.
    """
    sanitized = sanitize_audit_details(details)
    audit_entry = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=sanitized,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
