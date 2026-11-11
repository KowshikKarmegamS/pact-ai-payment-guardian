"""Brings a merchant connector's offers into PACT's catalog.

Offers become ordinary catalog products tagged with their source, so every platform faces the same
policy engine, approval fingerprint and PayPal flow. A sync that changes a price, name, merchant,
category or stock re-verifies every open proposal for that product, exactly like a manual catalog
edit; approvals that no longer match become APPROVAL_EXPIRED.
"""

from dataclasses import dataclass, field
from typing import List, Set

from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors import MerchantConnector
from app.models import Product, Proposal
from app.money import q
from app.services.audit import log_audit_event
from app.services.authorization import OPEN_STATUSES, recheck_open_proposals

_COMPARED = ("name", "description", "price", "category", "merchant", "in_stock", "image_url")


@dataclass
class SyncResult:
    connector_id: str
    offers: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    delisted: int = 0
    skipped: List[str] = field(default_factory=list)
    approvals_invalidated: int = 0


def _state(p: Product) -> dict:
    return {k: (f"{q(p.price):.2f}" if k == "price" else getattr(p, k)) for k in _COMPARED}


def sync_connector(db: Session, connector: MerchantConnector) -> SyncResult:
    """Raises ConnectorError (nothing is written) if the source cannot be read."""
    offers = connector.fetch_offers()
    result = SyncResult(connector_id=connector.id, offers=len(offers))
    currency = get_settings().currency.upper()
    existing = {p.external_id: p for p in db.query(Product).filter(Product.source == connector.id).all()}
    seen: Set[str] = set()
    changed_ids: List[int] = []

    for offer in offers:
        if offer.external_id in seen:
            result.skipped.append(f"{offer.name}: duplicate offer id {offer.external_id}.")
            continue
        seen.add(offer.external_id)
        if offer.currency.upper() != currency:
            result.skipped.append(f"{offer.name}: priced in {offer.currency}, PACT settles in {currency}.")
            continue
        values = {
            "name": offer.name[:255], "description": offer.description, "price": q(offer.price),
            "category": offer.category[:100], "merchant": offer.merchant[:100],
            "in_stock": offer.in_stock, "image_url": offer.image_url,
        }
        product = existing.get(offer.external_id)
        if product is None:
            db.add(Product(source=connector.id, external_id=offer.external_id, **values))
            result.created += 1
            continue
        before = _state(product)
        for k, v in values.items():
            setattr(product, k, v)
        if _state(product) != before:
            result.updated += 1
            changed_ids.append(product.id)
        else:
            result.unchanged += 1

    for external_id, product in existing.items():
        if external_id not in seen and product.in_stock:
            product.in_stock = False
            result.delisted += 1
            changed_ids.append(product.id)

    db.commit()

    if changed_ids:
        open_proposals = (
            db.query(Proposal)
            .filter(Proposal.product_id.in_(changed_ids), Proposal.status.in_(OPEN_STATUSES))
            .all()
        )
        result.approvals_invalidated = recheck_open_proposals(db, open_proposals, "merchant connector sync")

    log_audit_event(db, "CONNECTOR_SYNCED", "Connector", connector.id, {
        "connector": connector.name, "platform": connector.platform, "offers": result.offers,
        "created": result.created, "updated": result.updated, "unchanged": result.unchanged,
        "delisted": result.delisted, "skipped": result.skipped,
        "approvals_invalidated": result.approvals_invalidated,
    })
    return result
