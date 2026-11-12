"""PACT's authorization decision: AUTO_APPROVE, REQUIRES_APPROVAL or BLOCKED.

Deterministic and AI-free. It runs after the policy engine:

* BLOCKED: any policy rule failed (prohibited merchant or keyword, merchant or category not allowed, price,
  quantity or budget limit, expired/paused mandate, currency or integrity mismatch). No approval can override it.
* REQUIRES_APPROVAL: every rule passed, but the mandate asks the owner to approve every purchase, or the amount
  is above the owner's auto-authorization limit.
* AUTO_APPROVE: every rule passed, the mandate allows auto-authorization and the amount is within its limit.

PACT authorization is not payment: an auto-authorized purchase still goes through PayPal Checkout, where PayPal
requires the buyer's approval before PACT can capture.
"""

from decimal import Decimal
from typing import Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Mandate
from app.money import fmt, q
from app.schemas import PolicyResult

AUTO_APPROVE = "AUTO_APPROVE"
REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
BLOCKED = "BLOCKED"

MODE_APPROVAL_REQUIRED = "approval_required"
MODE_AUTO = "auto_approve_within_limits"
MODES = (MODE_APPROVAL_REQUIRED, MODE_AUTO)


def auto_enabled(mandate: Mandate) -> bool:
    return (mandate.authorization_mode or MODE_APPROVAL_REQUIRED) == MODE_AUTO and mandate.max_auto_approve_amount is not None


def decide(mandate: Mandate, policy: PolicyResult, total: Decimal, currency: str) -> Tuple[str, str]:
    if not policy.passed:
        return BLOCKED, "Blocked by policy: " + " ".join(policy.violations)
    rules = f"All {len(policy.checks)} policy rules passed"
    if not auto_enabled(mandate):
        return REQUIRES_APPROVAL, f"{rules}. This mandate requires your approval for every purchase."
    limit = q(mandate.max_auto_approve_amount)
    amount = q(total)
    if amount > limit:
        return REQUIRES_APPROVAL, (f"{rules}, but {fmt(amount, currency)} is above your {fmt(limit, currency)} "
                                   "auto-authorization limit, so it needs your approval.")
    return AUTO_APPROVE, (f"{rules} and {fmt(amount, currency)} is within your {fmt(limit, currency)} "
                          "auto-authorization limit. PayPal still requires the buyer's approval before payment.")


def lock_mandate_budget(db: Session, mandate: Mandate) -> None:
    """Serialize budget decisions for one mandate.

    Ends the current transaction, then makes a write to the mandate row the first statement of a new one.
    On SQLite that takes the database write lock; on Postgres a row lock. Until this transaction commits, any
    other request that wants to reserve budget on the same mandate waits here, so two concurrent purchases
    can never both be authorized against the same remaining budget. Callers commit to release.
    """
    db.commit()
    db.execute(text("UPDATE mandates SET budget_version = COALESCE(budget_version, 0) + 1 WHERE id = :id"),
               {"id": mandate.id})
    db.refresh(mandate)


def reservation_ref(proposal_id: str) -> str:
    return f"rsv-{proposal_id[:8]}"
