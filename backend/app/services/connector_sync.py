"""Brings merchant connector offers into PACT's catalog.

Offers become ordinary catalog products tagged with their source, so every platform faces the same
policy engine, approval fingerprint and PayPal flow. Any change to an offer's price, name, merchant,
category, stock or buy link re-verifies every open proposal for that product, exactly like a manual
catalog edit; approvals that no longer match become APPROVAL_EXPIRED. A source that cannot be read
changes nothing.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors import Channel3Connector, ConnectorError, MerchantConnector, Offer, get_connector
from app.connectors.base import stable_buy_link
from app.models import Product, Proposal, utc_now
from app.money import q
from app.services.audit import log_audit_event
from app.services.authorization import OPEN_STATUSES, recheck_open_proposals

_COMPARED = ("name", "description", "price", "category", "merchant", "in_stock", "image_url", "brand", "purchase_url")


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
    def val(k):
        if k == "price":
            return f"{q(p.price):.2f}"
        return stable_buy_link(getattr(p, k)) if k in ("purchase_url", "image_url") else getattr(p, k)
    return {k: val(k) for k in _COMPARED}


def _recheck(db: Session, product_ids: List[int], stage: str, exclude: Optional[str] = None) -> int:
    if not product_ids:
        return 0
    query = db.query(Proposal).filter(Proposal.product_id.in_(product_ids), Proposal.status.in_(OPEN_STATUSES))
    if exclude:
        query = query.filter(Proposal.id != exclude)
    return recheck_open_proposals(db, query.all(), stage)


def apply_offers(db: Session, connector: MerchantConnector, offers: List[Offer],
                 delist_missing: bool) -> Tuple[SyncResult, List[Product]]:
    """Upsert offers by (source, external_id). Returns the result and the products, in offer order."""
    result = SyncResult(connector_id=connector.id, offers=len(offers))
    currency = get_settings().currency.upper()
    existing = {p.external_id: p for p in db.query(Product).filter(Product.source == connector.id).all()}
    seen: Set[str] = set()
    changed_ids: List[int] = []
    touched: List[Product] = []
    now = utc_now()

    for offer in offers:
        if offer.external_id in seen:
            continue
        seen.add(offer.external_id)
        if offer.currency.upper() != currency:
            result.skipped.append(f"{offer.name}: priced in {offer.currency}, PACT settles in {currency}.")
            continue
        values = {
            "name": offer.name[:255], "description": offer.description, "price": q(offer.price),
            "category": offer.category[:100], "merchant": offer.merchant[:100],
            "in_stock": offer.in_stock, "image_url": offer.image_url,
            "brand": offer.brand, "purchase_url": offer.purchase_url,
        }
        product = existing.get(offer.external_id)
        if product is None:
            product = Product(source=connector.id, external_id=offer.external_id, offer_checked_at=now, **values)
            db.add(product)
            existing[offer.external_id] = product
            result.created += 1
        else:
            before = _state(product)
            for k, v in values.items():
                setattr(product, k, v)
            product.offer_checked_at = now
            if _state(product) != before:
                result.updated += 1
                changed_ids.append(product.id)
            else:
                result.unchanged += 1
        touched.append(product)

    if delist_missing:
        for external_id, product in existing.items():
            if external_id not in seen and product.in_stock:
                product.in_stock = False
                result.delisted += 1
                changed_ids.append(product.id)

    db.commit()
    for p in touched:
        db.refresh(p)
    result.approvals_invalidated = _recheck(db, changed_ids, f"{connector.name} sync")
    return result, touched


def sync_connector(db: Session, connector: MerchantConnector) -> SyncResult:
    """Raises ConnectorError (nothing is written) if the source cannot be read."""
    offers = connector.fetch_offers()
    result, _ = apply_offers(db, connector, offers, delist_missing=connector.full_feed)
    _audit_sync(db, connector, result)
    return result


def _audit_sync(db: Session, connector: MerchantConnector, result: SyncResult, query: Optional[str] = None) -> None:
    details = {
        "connector": connector.name, "platform": connector.platform, "offers": result.offers,
        "created": result.created, "updated": result.updated, "unchanged": result.unchanged,
        "delisted": result.delisted, "skipped": result.skipped,
        "approvals_invalidated": result.approvals_invalidated,
    }
    if query is not None:
        details["query"] = query[:200]
    log_audit_event(db, "CONNECTOR_SEARCHED" if query is not None else "CONNECTOR_SYNCED", "Connector", connector.id, details)


def search_and_import(db: Session, query: str, limit: int = 10, max_price=None) -> Tuple[SyncResult, List[Product]]:
    """Natural-language search through Channel3; matching offers become catalog items with PACT product IDs."""
    connector = get_connector("channel3")
    assert isinstance(connector, Channel3Connector)
    offers = connector.search(query, limit=limit, max_price=max_price)
    result, products = apply_offers(db, connector, offers, delist_missing=False)
    _audit_sync(db, connector, result, query=query)
    return result, products


def is_live_offer(product: Optional[Product]) -> bool:
    return product is not None and product.source == "channel3" and bool(product.external_id)


def refresh_offer(db: Session, product: Product, exclude_proposal: Optional[str] = None) -> List[str]:
    """Re-read one Channel3 offer right before an authorization step and update the catalog row.

    Returns the changes found. The caller's own verify_authorization() sees the new values and voids the
    approval if they differ from what was approved. Raises ConnectorError if Channel3 cannot confirm the offer,
    so callers fail closed.
    """
    connector = get_connector("channel3")
    assert isinstance(connector, Channel3Connector)
    c3_id, _, domain = (product.external_id or "").partition(":")
    try:
        offers = connector.product_offers(c3_id)
    except ConnectorError as exc:
        if getattr(exc, "status", None) != 404:
            raise
        offers = []
    match = next((o for o in offers if o.merchant == domain), None)

    before = _state(product)
    if match is None:
        product.in_stock = False
    else:
        product.name, product.description = match.name[:255], match.description
        product.price, product.category, product.merchant = q(match.price), match.category[:100], match.merchant[:100]
        product.in_stock, product.image_url = match.in_stock, match.image_url
        product.brand, product.purchase_url = match.brand, match.purchase_url
    product.offer_checked_at = utc_now()
    after = _state(product)
    db.commit()
    changes = [f"{k}: {before[k]!r} -> {after[k]!r}" for k in _COMPARED if before[k] != after[k] and k != "description"]
    if changes or match is None:
        log_audit_event(db, "CHANNEL3_OFFER_CHANGED", "Product", str(product.id), {
            "product_name": product.name, "merchant": product.merchant, "external_id": product.external_id,
            "offer_found": match is not None, "changes": changes,
        })
        _recheck(db, [product.id], "Channel3 offer check", exclude=exclude_proposal)
    return changes


def reverify_live_offer(db: Session, proposal: Proposal, product: Optional[Product], stage: str) -> None:
    """Before approval, PayPal order creation and capture: re-read a live offer from its retailer source.

    Raises ConnectorError when the offer cannot be confirmed, so the step is refused (fail closed).
    """
    if not is_live_offer(product):
        return
    try:
        refresh_offer(db, product, exclude_proposal=proposal.id)
    except ConnectorError as exc:
        log_audit_event(db, "CHANNEL3_OFFER_UNVERIFIED", "Proposal", proposal.id, {"stage": stage, "reason": str(exc)})
        raise
