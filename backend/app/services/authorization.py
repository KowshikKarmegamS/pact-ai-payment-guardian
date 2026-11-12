"""Approval binding and revalidation.

A proposal fingerprint is a SHA-256 hash over a canonical JSON snapshot of:
  * the exact purchase (product, merchant, category, unit price, quantity, total, currency)
  * the mandate's policy values (active flag, budget, allowlists, restrictions)

It is computed when the policy engine first evaluates the proposal, shown to the
human, sent back with their approval, and recomputed before PayPal order creation
and before capture. Any difference invalidates the approval.

Plain SHA-256 (not an HMAC) is deliberate: anyone can recompute it from the
receipt's values to check it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.base import stable_buy_link
from app.models import APPROVED_STATUSES, Mandate, Product, Proposal, ProposalStatus, as_utc, utc_now
from app.money import fmt, q
from app.policy import PolicyEngine, checks_to_json
from app.schemas import PolicyResult
from app.services.audit import log_audit_event
from app.services.mandate_service import budget_breakdown

FINGERPRINT_VERSION = 1


def _money(v: Any) -> str:
    return f"{q(v):.2f}"


def _canon_list(values: Any) -> List[str]:
    return sorted({str(v).strip().lower() for v in (values or []) if str(v).strip()})


def _canon_restrictions(r: Any) -> Dict[str, Any]:
    r = r if isinstance(r, dict) else {}
    out: Dict[str, Any] = {}
    for key in sorted(r.keys()):
        val = r[key]
        if val is None:
            continue
        if key in ("max_price_per_item", "min_price_per_item", "max_item_price", "min_item_price"):
            out[key] = _money(val)
        elif isinstance(val, list):
            out[key] = _canon_list(val)
        else:
            out[key] = val
    return out


def canonical_snapshot(proposal: Proposal, mandate: Mandate) -> Dict[str, Any]:
    snap = {
        "v": FINGERPRINT_VERSION,
        "proposal": {
            "id": proposal.id,
            "mandate_id": proposal.mandate_id,
            "product_id": int(proposal.product_id),
            "product_name": proposal.product_name,
            "merchant": proposal.merchant,
            "category": proposal.category,
            "unit_price": _money(proposal.price),
            "quantity": int(proposal.quantity),
            "total": _money(proposal.total_amount),
            "currency": (proposal.currency or "").upper(),
        },
        "mandate": {
            "id": mandate.id,
            "active": bool(mandate.is_active),
            "currency": (mandate.currency or "").upper(),
            "max_budget": _money(mandate.max_budget),
            "expires_at": as_utc(mandate.expires_at).isoformat(timespec="seconds") if mandate.expires_at else None,
            "allowed_merchants": _canon_list(mandate.allowed_merchants),
            "allowed_categories": _canon_list(mandate.allowed_categories),
            "restrictions": _canon_restrictions(mandate.restrictions),
        },
    }
    # Who asked is part of what the human approves. Added only when an external agent asked,
    # so fingerprints of earlier proposals are unchanged.
    if getattr(proposal, "agent_id", None):
        snap["requested_by"] = {"agent_id": proposal.agent_id, "agent_name": proposal.agent_name}
    # The exact external offer (retailer listing and buy link) is part of what the human approves.
    # Added only for connector offers, so fingerprints of catalog proposals are unchanged.
    if getattr(proposal, "offer_source", None) and getattr(proposal, "purchase_url", None):
        snap["offer"] = {"source": proposal.offer_source, "external_id": proposal.offer_external_id,
                         "purchase_url": stable_buy_link(proposal.purchase_url)}
    return snap


def fingerprint_of(snapshot: Dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_LABELS = {
    ("proposal", "product_id"): "Product",
    ("proposal", "product_name"): "Product name",
    ("proposal", "merchant"): "Merchant",
    ("proposal", "category"): "Category",
    ("proposal", "unit_price"): "Unit price",
    ("proposal", "quantity"): "Quantity",
    ("proposal", "total"): "Total amount",
    ("proposal", "currency"): "Currency",
    ("proposal", "mandate_id"): "Mandate",
    ("mandate", "active"): "Mandate active",
    ("mandate", "currency"): "Mandate currency",
    ("mandate", "max_budget"): "Mandate budget",
    ("mandate", "expires_at"): "Mandate expiry",
    ("mandate", "allowed_merchants"): "Allowed merchants",
    ("mandate", "allowed_categories"): "Allowed categories",
    ("mandate", "restrictions"): "Mandate restrictions",
    ("requested_by", "agent_id"): "Requesting agent",
    ("requested_by", "agent_name"): "Requesting agent name",
}


def describe_changes(before: Optional[Dict[str, Any]], after: Dict[str, Any]) -> List[str]:
    """Human-readable list of what differs between two canonical snapshots."""
    if not before:
        return ["No approved snapshot is on record for this proposal."]
    changes: List[str] = []
    for section in ("proposal", "mandate", "requested_by", "offer"):
        b, a = before.get(section) or {}, after.get(section) or {}
        for key in sorted(set(b) | set(a)):
            if b.get(key) != a.get(key):
                label = _LABELS.get((section, key), f"{section}.{key}")
                changes.append(f"{label} changed from {b.get(key)!r} to {a.get(key)!r}.")
    if before.get("v") != after.get("v"):
        changes.append("Fingerprint format version changed.")
    return changes


def catalog_drift(proposal: Proposal, product: Optional[Product]) -> List[str]:
    """Differences between the proposal's snapshot and the authoritative catalog."""
    if product is None:
        return ["The product no longer exists in the catalog."]
    drift = []
    if q(product.price) != q(proposal.price):
        drift.append(
            f"Catalog price changed from {fmt(proposal.price, proposal.currency)} to {fmt(product.price, proposal.currency)}."
        )
    if product.merchant != proposal.merchant:
        drift.append(f"Catalog merchant changed from '{proposal.merchant}' to '{product.merchant}'.")
    if product.category != proposal.category:
        drift.append(f"Catalog category changed from '{proposal.category}' to '{product.category}'.")
    if product.name != proposal.product_name:
        drift.append(f"Catalog product name changed from '{proposal.product_name}' to '{product.name}'.")
    if getattr(proposal, "purchase_url", None) and stable_buy_link(product.purchase_url) != stable_buy_link(proposal.purchase_url):
        drift.append("The retailer's buy link changed since this offer was approved.")
    return drift


@dataclass
class IntegrityResult:
    ok: bool
    current_fingerprint: str
    policy: PolicyResult
    changes: List[str] = field(default_factory=list)


def evaluate_for(db: Session, proposal: Proposal, mandate: Mandate, product: Optional[Product]) -> PolicyResult:
    """Run the policy engine with the budget available to this specific proposal."""
    _, _, remaining = budget_breakdown(db, mandate, exclude_proposal_id=proposal.id)
    return PolicyEngine.evaluate(
        mandate=mandate,
        proposal=proposal,
        product=product,
        remaining_budget=remaining,
        expected_currency=get_settings().currency,
    )


def verify_authorization(
    db: Session,
    proposal: Proposal,
    mandate: Mandate,
    product: Optional[Product],
    require_approval: bool = True,
) -> IntegrityResult:
    """Recompute the fingerprint, check catalog drift and re-run policy.

    Records the revalidation result on the proposal (caller commits).
    """
    snapshot = canonical_snapshot(proposal, mandate)
    current = fingerprint_of(snapshot)
    changes: List[str] = []

    if require_approval:
        if not proposal.approval_fingerprint or not proposal.approved_at:
            changes.append("No explicit human approval is recorded for this proposal.")
        elif current != proposal.approval_fingerprint:
            changes.extend(describe_changes(proposal.approval_snapshot, snapshot))
    else:
        if proposal.proposal_fingerprint and current != proposal.proposal_fingerprint:
            changes.extend(describe_changes(proposal.approval_snapshot, snapshot))

    changes.extend(catalog_drift(proposal, product))

    policy = evaluate_for(db, proposal, mandate, product)
    proposal.revalidation_checks = checks_to_json(policy)
    proposal.revalidated_at = utc_now()

    return IntegrityResult(
        ok=not changes and policy.passed,
        current_fingerprint=current,
        policy=policy,
        changes=changes,
    )


def expire_approval(db: Session, proposal: Proposal, stage: str, result: IntegrityResult) -> str:
    """Invalidate an approval, record why, and return the user-facing explanation."""
    reasons = result.changes + result.policy.violations
    message = (
        f"Approval invalidated before {stage}: "
        + " ".join(reasons)
        + " A fresh policy evaluation and explicit human approval are required."
    )
    previous = proposal.status
    proposal.status = ProposalStatus.APPROVAL_EXPIRED
    proposal.status_reason = message
    proposal.capture_lock_expires = None
    db.commit()
    log_audit_event(
        db,
        "APPROVAL_INVALIDATED",
        "Proposal",
        proposal.id,
        {
            "stage": stage,
            "previous_status": previous.value if hasattr(previous, "value") else str(previous),
            "changes": result.changes,
            "violations": result.policy.violations,
            "approved_fingerprint": proposal.approval_fingerprint,
            "current_fingerprint": result.current_fingerprint,
        },
    )
    return message


def recheck_open_proposals(db: Session, proposals: List[Proposal], stage: str) -> int:
    """Re-verify proposals that are awaiting approval or hold a live approval.

    Used whenever something they depend on changes (mandate edit, revoke, catalog price).
    Returns how many were invalidated.
    """
    invalidated = 0
    for proposal in proposals:
        mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
        product = db.query(Product).filter(Product.id == proposal.product_id).first()
        if mandate is None:
            continue
        approved = proposal.status in APPROVED_STATUSES
        result = verify_authorization(db, proposal, mandate, product, require_approval=approved)
        if result.ok:
            db.commit()
        else:
            expire_approval(db, proposal, stage, result)
            invalidated += 1
    return invalidated


OPEN_STATUSES = tuple(APPROVED_STATUSES) + (ProposalStatus.AWAITING_HUMAN_APPROVAL,)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None
