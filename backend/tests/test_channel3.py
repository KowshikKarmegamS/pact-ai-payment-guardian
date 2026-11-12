"""Channel3 live retailer offers: search, normalization, policy, fingerprint binding, stale offers, handoff.

The Channel3 HTTP API is replaced by an httpx.MockTransport; tests never reach the real service.
"""

import copy
import json
from decimal import Decimal

import httpx
import pytest

from app import connectors as registry
from app.config import get_settings
from app.connectors.channel3 import normalize_product
from app.models import AuditLog, Mandate, Product, Proposal, ProposalStatus
from app.services.authorization import canonical_snapshot

KEY = "c3-test-key-not-real"


def _offer(domain, price, available=True, currency="USD", url=None):
    return {"url": url or f"https://buy.trychannel3.com/mx3s-{domain}", "domain": domain,
            "price": {"price": price, "compare_at_price": None, "currency": currency},
            "availability": "InStock" if available else "OutOfStock", "condition": "new"}


MOUSE = {
    "id": "nLZKmNT", "title": "Logitech MX Master 3S Performance Wireless Mouse",
    "description": "Quiet clicks and 8K DPI tracking.",
    "brands": [{"id": "b1", "name": "Logitech"}],
    "images": [{"url": "https://cdn.trychannel3.com/mx3s.jpg", "is_main_image": True}],
    "category": {"slug": "mice", "title": "Mice",
                 "path": [{"slug": "electronics", "title": "Electronics"}, {"slug": "mice", "title": "Mice"}]},
    "offers": [_offer("bestbuy.com", 99.99), _offer("newegg.com", 62.99), _offer("6ave.com", 544.95)],
}


class FakeChannel3:
    def __init__(self):
        self.products = {MOUSE["id"]: copy.deepcopy(MOUSE)}
        self.calls = []
        self.fail = None  # e.g. 429, 500, "timeout"
        self.rotate_aid = False  # real Channel3 links carry a per-request attribution id

    def _payload(self, product):
        if not self.rotate_aid:
            return product
        p = copy.deepcopy(product)
        for o in p["offers"]:
            o["url"] = f"{o['url']}?o=O{len(self.calls)}&aid=A{len(self.calls)}"
        return p

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.fail == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if self.fail:
            return httpx.Response(self.fail, json={"detail": "nope"})
        if request.method == "POST" and request.url.path == "/v1/search":
            return httpx.Response(200, json={"products": [self._payload(p) for p in self.products.values()],
                                             "next_page_token": None})
        if request.method == "GET" and request.url.path.startswith("/v1/products/"):
            pid = request.url.path.rsplit("/", 1)[1]
            if pid not in self.products:
                return httpx.Response(404, json={"detail": "Product not found"})
            return httpx.Response(200, json=self._payload(self.products[pid]))
        return httpx.Response(404, json={"detail": "unknown"})

    def set_offer(self, domain, **changes):
        for o in self.products[MOUSE["id"]]["offers"]:
            if o["domain"] == domain:
                if "price" in changes:
                    o["price"]["price"] = changes["price"]
                if "available" in changes:
                    o["availability"] = "InStock" if changes["available"] else "OutOfStock"
                if "url" in changes:
                    o["url"] = changes["url"]


@pytest.fixture
def c3(monkeypatch):
    fake = FakeChannel3()
    monkeypatch.setattr(get_settings(), "CHANNEL3_API_KEY", KEY)
    monkeypatch.setattr(registry.CONNECTORS["channel3"], "_transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def retail_mandate(db_session):
    m = Mandate(name="Live retailers", max_budget=Decimal("300.00"), currency="USD",
                allowed_merchants=["bestbuy.com", "newegg.com"], allowed_categories=["Electronics"],
                restrictions={"max_price_per_item": 100.00, "max_quantity": 2}, is_active=True)
    db_session.add(m)
    db_session.commit()
    return m


def _search(client, query="logitech mx master 3s"):
    res = client.post("/api/connectors/channel3/search", json={"query": query, "limit": 5})
    assert res.status_code == 200, res.text
    return res.json()


def _product(db, domain):
    return db.query(Product).filter(Product.source == "channel3", Product.merchant == domain).one()


def _propose(client, mandate, product):
    res = client.post("/api/proposals/propose", json={"mandate_id": mandate.id, "product_id": product.id})
    assert res.status_code == 201, res.text
    return res.json()["proposal"]


def _approve(client, p):
    return client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})


# ----------------------------------------------------------------------------- normalization

def test_normalize_one_offer_per_retailer():
    raw = copy.deepcopy(MOUSE)
    raw["offers"] += [_offer("eu-shop.de", 70.0, currency="EUR"), _offer("plain.com", 50.0, url="http://plain.com/x"),
                      _offer("bestbuy.com", 1.0)]  # duplicate retailer: first one wins
    offers = normalize_product(raw, "USD")
    assert [o.merchant for o in offers] == ["bestbuy.com", "newegg.com", "6ave.com"]
    o = offers[0]
    assert (o.external_id, o.price, o.category, o.brand, o.in_stock) == \
        ("nLZKmNT:bestbuy.com", Decimal("99.99"), "Electronics", "Logitech", True)
    assert o.purchase_url == "https://buy.trychannel3.com/mx3s-bestbuy.com"
    assert o.image_url == "https://cdn.trychannel3.com/mx3s.jpg"
    assert normalize_product({"id": "x", "title": "", "offers": [_offer("a.com", 5)]}, "USD") == []


# ----------------------------------------------------------------------------- search + import

def test_search_imports_real_offer_fields_and_sends_key_only_in_header(client, db_session, c3):
    body = _search(client)
    assert body["result"]["created"] == 3
    names = {p["merchant"]: p for p in body["products"]}
    assert names["newegg.com"]["price"] == "62.99" and names["newegg.com"]["source"] == "channel3"
    assert names["bestbuy.com"]["purchase_url"].startswith("https://buy.trychannel3.com/")
    assert names["6ave.com"]["external_id"] == "nLZKmNT:6ave.com"

    req = c3.calls[0]
    assert req.headers["x-api-key"] == KEY
    assert KEY not in str(req.url)
    assert json.loads(req.content)["query"] == "logitech mx master 3s"

    again = _search(client)
    assert again["result"]["created"] == 0 and again["result"]["unchanged"] == 3
    assert db_session.query(Product).filter(Product.source == "channel3").count() == 3
    logged = " ".join(json.dumps(a.details) for a in db_session.query(AuditLog).all())
    assert "CONNECTOR_SEARCHED" in {a.event_type for a in db_session.query(AuditLog).all()}
    assert KEY not in logged and KEY not in json.dumps(body)


def test_not_configured_and_upstream_errors(client, c3, monkeypatch, db_session):
    for status, expected in ((401, 502), (402, 502), (429, 503), (500, 502), ("timeout", 504)):
        c3.fail = status
        res = client.post("/api/connectors/channel3/search", json={"query": "mouse"})
        assert res.status_code == expected, (status, res.text)
    assert db_session.query(Product).filter(Product.source == "channel3").count() == 0
    monkeypatch.setattr(get_settings(), "CHANNEL3_API_KEY", "")
    assert client.post("/api/connectors/channel3/search", json={"query": "mouse"}).status_code == 503
    listed = {c["id"]: c for c in client.get("/api/connectors").json()}
    assert listed["channel3"]["configured"] is False and listed["channel3"]["searchable"] is True


# ----------------------------------------------------------------------------- policy + fingerprint

def test_external_offers_face_the_mandate(client, db_session, c3, retail_mandate):
    _search(client)
    ok = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    assert ok["status"] == "AWAITING_HUMAN_APPROVAL" and ok["merchant"] == "bestbuy.com"
    bad = client.post("/api/proposals/propose", json={"mandate_id": retail_mandate.id,
                                                      "product_id": _product(db_session, "6ave.com").id}).json()
    assert bad["proposal"]["status"] == "POLICY_REJECTED"
    failed = {c["rule"] for c in bad["policy"]["checks"] if not c["passed"]}
    assert {"merchant_allowlist"} <= failed
    assert any("544.95" in v for v in bad["policy"]["violations"])
    too_many = client.post("/api/proposals/propose", json={"mandate_id": retail_mandate.id, "quantity": 3,
                                                           "product_id": _product(db_session, "newegg.com").id}).json()
    assert too_many["proposal"]["status"] == "POLICY_REJECTED"


def test_fingerprint_binds_the_exact_retailer_offer(client, db_session, c3, retail_mandate, sample_mandate, sample_product):
    _search(client)
    p = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    row = db_session.get(Proposal, p["id"])
    snap = canonical_snapshot(row, retail_mandate)
    assert snap["offer"] == {"source": "channel3", "external_id": "nLZKmNT:bestbuy.com",
                             "purchase_url": "https://buy.trychannel3.com/mx3s-bestbuy.com"}
    catalog_p = _propose(client, sample_mandate, sample_product)
    assert "offer" not in canonical_snapshot(db_session.get(Proposal, catalog_p["id"]), sample_mandate)


# ----------------------------------------------------------------------------- stale offers

def test_price_change_at_retailer_voids_approval(client, db_session, c3, retail_mandate):
    _search(client)
    p = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    c3.set_offer("bestbuy.com", price=94.50)
    res = _approve(client, p)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "APPROVAL_INVALIDATED"
    assert "99.99" in res.json()["detail"]["message"] and "94.50" in res.json()["detail"]["message"]
    db_session.expire_all()
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.APPROVAL_EXPIRED
    assert "CHANNEL3_OFFER_CHANGED" in {a.event_type for a in db_session.query(AuditLog).all()}


def test_offer_gone_or_link_changed_voids_and_unreachable_fails_closed(client, db_session, c3, retail_mandate, fake_paypal):
    _search(client)
    # Retailer removed the offer -> out of stock -> policy fails.
    a = _propose(client, retail_mandate, _product(db_session, "newegg.com"))
    c3.products[MOUSE["id"]]["offers"] = [o for o in c3.products[MOUSE["id"]]["offers"] if o["domain"] != "newegg.com"]
    assert _approve(client, a).status_code == 409

    # Approved, then the buy link changes -> PayPal order creation refused, PayPal never called.
    b = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    assert _approve(client, b).status_code == 200
    c3.set_offer("bestbuy.com", url="https://buy.trychannel3.com/somewhere-else")
    res = client.post(f"/api/payments/{b['id']}/create-order")
    assert res.status_code == 409 and fake_paypal.create_calls == 0

    # Channel3 unreachable at approval -> 503, nothing approved.
    c3.set_offer("bestbuy.com", url="https://buy.trychannel3.com/mx3s-bestbuy.com")
    _search(client)
    c = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    c3.fail = 500
    res = _approve(client, c)
    assert res.status_code == 503 and res.json()["detail"]["code"] == "OFFER_UNVERIFIED"
    db_session.expire_all()
    assert db_session.get(Proposal, c["id"]).status == ProposalStatus.AWAITING_HUMAN_APPROVAL


# ----------------------------------------------------------------------------- PayPal + handoff

def test_paypal_capture_then_retailer_handoff(client, db_session, c3, retail_mandate, fake_paypal, sample_mandate, sample_product):
    _search(client)
    p = _propose(client, retail_mandate, _product(db_session, "newegg.com"))
    assert client.post(f"/api/payments/{p['id']}/retailer-handoff").status_code == 409  # not captured yet
    assert _approve(client, p).status_code == 200
    order = client.post(f"/api/payments/{p['id']}/create-order").json()
    assert fake_paypal.last_create_kwargs["merchant"] == "newegg.com"
    fake_paypal.buyer_approves(order["order_id"])

    c3.fail = 503  # offer cannot be re-checked -> capture refused, nothing charged
    assert client.post(f"/api/payments/{p['id']}/capture").status_code == 503
    assert fake_paypal.capture_calls == 0
    c3.fail = None
    cap = client.post(f"/api/payments/{p['id']}/capture")
    assert cap.status_code == 200, cap.text
    assert cap.json()["proposal"]["status"] == "CAPTURED"

    h = client.post(f"/api/payments/{p['id']}/retailer-handoff")
    assert h.status_code == 200, h.text
    body = h.json()
    assert body["url"] == "https://buy.trychannel3.com/mx3s-newegg.com" and body["merchant"] == "newegg.com"
    assert body["payment_status"] == "CAPTURED"
    db_session.expire_all()
    row = db_session.get(Proposal, p["id"])
    assert row.status == ProposalStatus.CAPTURED and row.retailer_handoff_at is not None
    events = [a.event_type for a in db_session.query(AuditLog).filter(AuditLog.entity_id == p["id"])]
    assert "RETAILER_HANDOFF_OPENED" in events and events.count("PAYPAL_PAYMENT_CAPTURED") == 1

    catalog_p = _propose(client, sample_mandate, sample_product)
    assert client.post(f"/api/payments/{catalog_p['id']}/retailer-handoff").json()["detail"]["code"] == "NO_RETAILER"


# ----------------------------------------------------------------------------- agents + reference agent

def test_agent_gateway_live_search_never_exposes_buy_links(client, db_session, c3, retail_mandate):
    agent = client.post("/api/agents", json={"name": "Claude Desktop (MCP)", "mandate_ids": [retail_mandate.id]}).json()
    h = {"Authorization": f"Bearer {agent['api_key']}"}
    res = client.get("/api/agent/v1/catalog", params={"q": "mx master mouse", "limit": 5}, headers=h)
    assert res.status_code == 200, res.text
    items = res.json()
    live = [i for i in items if i["source"] == "channel3"]
    assert {i["merchant"] for i in live} == {"bestbuy.com", "newegg.com", "6ave.com"}
    assert all("purchase_url" not in i and "buy.trychannel3" not in json.dumps(i) for i in items)

    newegg = next(i for i in live if i["merchant"] == "newegg.com")
    req = client.post("/api/agent/v1/purchases", headers=h, json={
        "mandate_id": retail_mandate.id, "product_id": newegg["product_id"], "reason": "User wants this mouse"})
    assert req.status_code == 201 and req.json()["decision"] == "PENDING_HUMAN"

    c3.fail = 500
    res = client.get("/api/agent/v1/catalog", params={"q": "usb hub"}, headers=h)
    assert res.status_code == 200 and res.headers.get("X-PACT-Live-Search") == "unavailable"


def test_reference_agent_live_mode_picks_from_channel3(client, db_session, c3, retail_mandate):
    res = client.post("/api/proposals/generate", json={"prompt": "logitech mx master mouse from newegg",
                                                        "mandate_id": retail_mandate.id, "source": "channel3"})
    assert res.status_code == 201, res.text
    p = res.json()["proposal"]
    assert p["offer_source"] == "channel3" and p["merchant"] in {"bestbuy.com", "newegg.com", "6ave.com"}
    c3.fail = 429
    res = client.post("/api/proposals/generate", json={"prompt": "mouse", "mandate_id": retail_mandate.id,
                                                        "source": "channel3"})
    assert res.status_code == 503 and res.json()["detail"]["code"] == "CHANNEL3_UNAVAILABLE"


def test_rotating_attribution_id_does_not_void_a_valid_approval(client, db_session, c3, retail_mandate, fake_paypal):
    c3.rotate_aid = True
    _search(client)
    p = _propose(client, retail_mandate, _product(db_session, "bestbuy.com"))
    assert _approve(client, p).status_code == 200
    res = client.post(f"/api/payments/{p['id']}/create-order")
    assert res.status_code == 200, res.text
    assert "CHANNEL3_OFFER_CHANGED" not in {a.event_type for a in db_session.query(AuditLog).all()}
    # The offer id itself changing is a different listing: still voids.
    c3.set_offer("bestbuy.com", url="https://buy.trychannel3.com/other-listing")
    fake_paypal.buyer_approves(res.json()["order_id"])
    assert client.post(f"/api/payments/{p['id']}/capture").status_code == 409
    assert fake_paypal.capture_calls == 0
