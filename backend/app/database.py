"""Database engine, session management, table initialization and light migrations."""

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

logger = logging.getLogger("pact.db")
settings = get_settings()

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # Ensure the directory for a file-based SQLite DB exists (e.g. a mounted disk).
    db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. (table, column, SQL type + default)
_ADDITIVE_COLUMNS = [
    ("mandates", "currency", "VARCHAR(3) NOT NULL DEFAULT 'USD'"),
    ("mandates", "expires_at", "DATETIME"),
    ("mandates", "revoked_at", "DATETIME"),
    ("proposals", "alternatives", "JSON"),
    ("proposals", "currency", "VARCHAR(3) NOT NULL DEFAULT 'USD'"),
    ("proposals", "status_reason", "TEXT"),
    ("proposals", "user_prompt", "TEXT"),
    ("proposals", "ai_provider", "VARCHAR(32)"),
    ("proposals", "ai_model", "VARCHAR(100)"),
    ("proposals", "ai_fallback_reason", "TEXT"),
    ("proposals", "supersedes_id", "VARCHAR(36)"),
    ("proposals", "policy_checks", "JSON"),
    ("proposals", "remaining_budget_at_decision", "NUMERIC(10, 2)"),
    ("proposals", "revalidation_checks", "JSON"),
    ("proposals", "revalidated_at", "DATETIME"),
    ("proposals", "proposal_fingerprint", "VARCHAR(64)"),
    ("proposals", "approval_fingerprint", "VARCHAR(64)"),
    ("proposals", "approval_snapshot", "JSON"),
    ("proposals", "approved_at", "DATETIME"),
    ("proposals", "paypal_order_status", "VARCHAR(40)"),
    ("proposals", "paypal_capture_status", "VARCHAR(40)"),
    ("proposals", "captured_amount", "NUMERIC(10, 2)"),
    ("proposals", "captured_currency", "VARCHAR(3)"),
    ("proposals", "captured_at", "DATETIME"),
    ("proposals", "paypal_debug_id", "VARCHAR(100)"),
    ("proposals", "capture_lock_expires", "FLOAT"),
]


def migrate_schema(bind: Engine) -> None:
    """Additive, non-destructive migration for databases created by earlier versions.

    Adds missing columns and maps legacy status values onto the new state machine.
    Legacy approvals carry no integrity fingerprint, so they are expired and must be
    re-evaluated; legacy "captured" rows were never verified against PayPal, so they
    are moved to CAPTURE_PENDING where the verify endpoint reconciles them with PayPal.
    """
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    with bind.begin() as conn:
        for table, column, ddl in _ADDITIVE_COLUMNS:
            if table not in tables:
                continue
            existing = {c["name"] for c in inspect(conn).get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info("Migrated schema: added %s.%s", table, column)

        if "proposals" not in tables:
            return

        legacy = {
            "PENDING": ("AWAITING_HUMAN_APPROVAL", None),
            "APPROVED": (
                "APPROVAL_EXPIRED",
                "Approved by an earlier PACT version without an integrity fingerprint. Re-evaluate to continue.",
            ),
            "CAPTURED": (
                "CAPTURE_PENDING",
                "Legacy capture record has not been verified with PayPal. Use 'Verify with PayPal'.",
            ),
            "FAILED": ("PAYMENT_FAILED", None),
        }
        for old, (new, reason) in legacy.items():
            conn.execute(
                text("UPDATE proposals SET status = :new, status_reason = COALESCE(:reason, status_reason) WHERE status = :old"),
                {"new": new, "old": old, "reason": reason},
            )
        # Legacy REJECTED covered both policy and human rejections.
        conn.execute(text(
            "UPDATE proposals SET status = 'HUMAN_REJECTED' WHERE status = 'REJECTED' AND id IN "
            "(SELECT entity_id FROM audit_logs WHERE event_type = 'PROPOSAL_HUMAN_REJECTED')"
        ))
        conn.execute(text("UPDATE proposals SET status = 'POLICY_REJECTED' WHERE status = 'REJECTED'"))


def init_db(bind: Engine = engine) -> None:
    """Create all tables if they do not exist, then apply additive migrations."""
    import app.models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=bind)
    migrate_schema(bind)
