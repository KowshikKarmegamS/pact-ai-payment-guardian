"""Merchant connectors: offers from other platforms enter the catalog and face the same controls."""

import json
from decimal import Decimal

import pytest

from app import connectors as registry
from app.connectors.shopify_feed import ShopifyFeedConnector
from app.models import AuditLog, Mandate, Product, Proposal, ProposalStatus


def _feed(path, products):
    path.write_text(json.dumps({"products": products}), encoding="utf-8")


def _item(pid, title, price, available=True, ptype="Office", variant="Default Title", vid=None):
    return {"id": pid, "title": title, "body_html": "<p>Nice <b>thing</b></p>", "product_type": ptype,
            "variants": [{"id": vid or pid * 10, "title": variant, "price": price, "available": available}]}


@pytest.fixture
def store(tmp_path, monkeypatch):
    feed = tmp_path / "store.json"
    _feed(feed, [_item(1, "Laptop Stand", "39.99"), _item(2, "Desk Mat", "24.00", available=False)])
    conn = ShopifyFeedConnector(id="test-store", store_name="Test Store", feed=feed)
    monkeypatch.setattr(registry, "CONNECTORS", {conn.id: conn})
    return feed


@pytest.fixture
def store_mandate(db_session):
    m = Mandate(name="Store mandate", max_budget=Decimal("200.00"), currency="USD",
                allowed_merchants=["Test Store"], allowed_categories=["Office"],
                restrictions={"max_price_per_item": 100.00}, is_active=True)
    db_session.add(m)
    db_session.commit()
    return m


def _sync(client, cid="test-store"):
    res = client.post(f"/api/connectors/{cid}/sync")
    assert res.status_code == 200, res.text
    return res.json()


def _approved(client, db_session, mandate):
    product = db_session.query(Product).filter(Product.name == "Laptop Stand").one()
    res = client.post("/api/proposals/propose", json={"mandate_id": mandate.id, "product_id": product.id})
    assert res.status_code == 201, res.text
    p = res.json()["proposal"]
    assert p["merchant"] == "Test Store"
    res = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    assert res.status_code == 200, res.text
    return p["id"]


def test_shopify_feed_parsing(tmp_path):
    feed = tmp_path / "f.json"
    _feed(feed, [
        _item(1, "Mat", "24", variant="Charcoal"),
        _item(2, "Broken price", "abc"),
        _item(3, "Free thing", "0.00"),
        {"id": 4, "title": "", "variants": [{"id": 1, "price": "5"}]},
    ])
    offers = ShopifyFeedConnector("s", "Shop", feed).fetch_offers()
    assert len(offers) == 1
    o = offers[0]
    assert (o.name, o.price, o.merchant, o.category, o.description, o.external_id) == \
        ("Mat (Charcoal)", Decimal("24.00"), "Shop", "Office", "Nice thing", "1:10")


def test_sync_imports_offers_with_source(client, db_session, store):
    r = _sync(client)
    assert (r["offers"], r["created"], r["updated"]) == (2, 2, 0)
    rows = db_session.query(Product).filter(Product.source == "test-store").all()
    assert {p.merchant for p in rows} == {"Test Store"}
    assert {p.name: p.in_stock for p in rows} == {"Laptop Stand": True, "Desk Mat": False}

    again = _sync(client)
    assert (again["created"], again["updated"], again["unchanged"]) == (0, 0, 2)

    listed = {c["id"]: c for c in client.get("/api/connectors").json()}
    assert listed["test-store"]["products"] == 2 and listed["test-store"]["in_stock"] == 1
    assert listed["test-store"]["last_synced_at"] is not None
    assert listed["pact-catalog"]["syncable"] is False
    assert client.get("/api/products").json()[0]["source"] == "test-store"
    assert db_session.query(AuditLog).filter(AuditLog.event_type == "CONNECTOR_SYNCED").count() == 2


def test_synced_offer_faces_policy_and_fingerprint(client, db_session, store, store_mandate):
    _sync(client)
    pid = _approved(client, db_session, store_mandate)

    _feed(store, [_item(1, "Laptop Stand", "45.00"), _item(2, "Desk Mat", "24.00", available=False)])
    r = _sync(client)
    assert r["updated"] == 1 and r["approvals_invalidated"] == 1
    db_session.expire_all()
    p = db_session.get(Proposal, pid)
    assert p.status == ProposalStatus.APPROVAL_EXPIRED
    assert "39.99" in p.status_reason and "45.00" in p.status_reason


def test_delisted_offer_goes_out_of_stock_and_voids_approval(client, db_session, store, store_mandate):
    _sync(client)
    pid = _approved(client, db_session, store_mandate)
    _feed(store, [_item(2, "Desk Mat", "24.00")])
    r = _sync(client)
    assert r["delisted"] == 1 and r["approvals_invalidated"] == 1
    db_session.expire_all()
    assert db_session.get(Proposal, pid).status == ProposalStatus.APPROVAL_EXPIRED


def test_merchant_not_on_mandate_is_blocked(client, db_session, store, sample_mandate):
    _sync(client)
    product = db_session.query(Product).filter(Product.name == "Laptop Stand").one()
    res = client.post("/api/proposals/propose", json={"mandate_id": sample_mandate.id, "product_id": product.id})
    assert res.status_code == 201
    assert res.json()["proposal"]["status"] == "POLICY_REJECTED"


def test_foreign_currency_and_bad_feed(client, db_session, store, monkeypatch):
    conn = registry.CONNECTORS["test-store"]
    monkeypatch.setattr(conn, "currency", "EUR")
    r = _sync(client)
    assert r["created"] == 0 and len(r["skipped"]) == 2

    store.write_text("not json", encoding="utf-8")
    res = client.post("/api/connectors/test-store/sync")
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "CONNECTOR_UNAVAILABLE"
    assert db_session.query(Product).filter(Product.source == "test-store").count() == 0


def test_unknown_connector(client, store):
    assert client.post("/api/connectors/nope/sync").status_code == 404


def test_bundled_demo_feed_is_valid():
    conn = ShopifyFeedConnector("x", "Northwind Supply",
                                registry._FEEDS / "northwind-supply.products.json")
    offers = conn.fetch_offers()
    assert len(offers) == 7 and all(o.price > 0 for o in offers)
