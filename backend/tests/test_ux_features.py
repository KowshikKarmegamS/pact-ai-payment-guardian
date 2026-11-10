"""Mandate expiry and revocation, catalog changes, alternatives, receipt budget facts."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import AuditLog, Product, Proposal, ProposalStatus
from app.policy import PolicyEngine


def _gen(client, mandate_id, prompt="USB-C hub adapter from TechHub"):
    res = client.post("/api/proposals/generate", json={"prompt": prompt, "mandate_id": mandate_id})
    assert res.status_code == 201, res.text
    return res.json()


def _approve(client, p):
    res = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    assert res.status_code == 200, res.text
    return res.json()


def _future(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ---------------- expiry ----------------

def test_policy_blocks_expired_mandate_pure():
    mandate = {"is_active": True, "max_budget": Decimal("100"), "allowed_merchants": ["TechHub"],
               "allowed_categories": ["Electronics"], "restrictions": {},
               "expires_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    proposal = {"merchant": "TechHub", "category": "Electronics", "product_name": "Hub",
                "price": Decimal("10"), "quantity": 1, "total_amount": Decimal("10")}
    before = PolicyEngine.evaluate(mandate, proposal, now=datetime(2025, 12, 31, tzinfo=timezone.utc))
    after = PolicyEngine.evaluate(mandate, proposal, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert before.passed
    assert not after.passed
    assert any("expired" in v for v in after.violations)
    assert "mandate_not_expired" in [c.rule for c in after.checks]


def test_mandate_expiry_must_be_in_future(client):
    res = client.post("/api/mandates", json={
        "name": "Old", "max_budget": "50.00", "allowed_merchants": ["TechHub"], "allowed_categories": ["Electronics"],
        "expires_at": "2020-01-01T00:00:00Z"})
    assert res.status_code == 422


def test_mandate_expiry_roundtrip_and_clear(client, sample_mandate):
    res = client.put(f"/api/mandates/{sample_mandate.id}", json={"expires_at": _future()})
    assert res.status_code == 200
    assert res.json()["expires_at"] is not None and res.json()["status"] == "active"
    res = client.put(f"/api/mandates/{sample_mandate.id}", json={"expires_at": None})
    assert res.json()["expires_at"] is None


def test_setting_expiry_invalidates_existing_approval(client, sample_mandate, sample_product, db_session):
    p = _gen(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    client.put(f"/api/mandates/{sample_mandate.id}", json={"expires_at": _future()})
    prop = db_session.get(Proposal, p["id"])
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.APPROVAL_EXPIRED
    assert "Mandate expiry changed" in prop.status_reason


# ---------------- revoke ----------------

def test_revoke_is_permanent_and_invalidates_approvals(client, sample_mandate, sample_product, db_session):
    p = _gen(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    res = client.post(f"/api/mandates/{sample_mandate.id}/revoke")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "revoked" and body["is_active"] is False and body["revoked_at"]

    prop = db_session.get(Proposal, p["id"])
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.APPROVAL_EXPIRED

    # Cannot be resumed or edited, and new proposals are blocked.
    assert client.put(f"/api/mandates/{sample_mandate.id}", json={"is_active": True}).status_code == 409
    assert _gen(client, sample_mandate.id)["proposal"]["status"] == "POLICY_REJECTED"
    events = [a.event_type for a in db_session.query(AuditLog).filter(AuditLog.entity_id == sample_mandate.id)]
    assert "MANDATE_REVOKED" in events


# ---------------- catalog price change ----------------

def test_price_change_invalidates_approved_and_pending(client, sample_mandate, sample_product, fake_paypal, db_session):
    approved = _gen(client, sample_mandate.id)["proposal"]
    _approve(client, approved)
    order = client.post(f"/api/payments/{approved['id']}/create-order").json()
    fake_paypal.buyer_approves(order["order_id"])
    pending = _gen(client, sample_mandate.id)["proposal"]

    res = client.put(f"/api/products/{sample_product.id}", json={"price": "44.99"})
    assert res.status_code == 200
    assert res.json()["approvals_invalidated"] == 2
    assert Decimal(res.json()["product"]["price"]) == Decimal("44.99")

    for pid in (approved["id"], pending["id"]):
        prop = db_session.get(Proposal, pid)
        db_session.refresh(prop)
        assert prop.status == ProposalStatus.APPROVAL_EXPIRED
        assert "Catalog price changed from $34.99 to $44.99" in prop.status_reason

    # The old approval cannot be used to pay the new price.
    assert client.post(f"/api/payments/{approved['id']}/capture").status_code == 409
    assert fake_paypal.capture_calls == 0

    # Re-evaluation produces a fresh proposal at the new price that needs a new approval.
    new = client.post(f"/api/proposals/{approved['id']}/re-evaluate").json()["proposal"]
    assert Decimal(new["price"]) == Decimal("44.99")
    assert new["status"] == "AWAITING_HUMAN_APPROVAL"
    assert new["approved_at"] is None

    events = [a.event_type for a in db_session.query(AuditLog).filter(AuditLog.entity_type == "Product")]
    assert events == ["CATALOG_PRODUCT_CHANGED"]


def test_price_change_does_not_touch_captured(client, sample_mandate, sample_product, fake_paypal, db_session):
    p = _gen(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    order = client.post(f"/api/payments/{p['id']}/create-order").json()
    fake_paypal.buyer_approves(order["order_id"])
    assert client.post(f"/api/payments/{p['id']}/capture").json()["proposal"]["status"] == "CAPTURED"
    res = client.put(f"/api/products/{sample_product.id}", json={"price": "99.00"})
    assert res.json()["approvals_invalidated"] == 0
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.CAPTURED


def test_product_update_validation(client, sample_product):
    assert client.put(f"/api/products/{sample_product.id}", json={"price": "-1"}).status_code == 422
    assert client.put("/api/products/99999", json={"price": "5.00"}).status_code == 404


# ---------------- alternatives and user-selected proposals ----------------

def test_alternatives_have_deterministic_eligibility(client, sample_mandate, sample_product, db_session):
    db_session.add_all([
        Product(name="Anker USB-C Hub Pro 10-in-1", description="Bigger USB-C hub adapter", price=Decimal("64.99"),
                category="Electronics", merchant="TechHub", in_stock=True),
        Product(name="Shady USB-C Hub", description="USB-C hub adapter", price=Decimal("9.99"),
                category="Electronics", merchant="UnknownSeller", in_stock=True),
    ])
    db_session.commit()
    p = _gen(client, sample_mandate.id)["proposal"]
    alts = {a["name"]: a for a in p["alternatives"]}
    # Whichever Anker hub was not chosen is offered as an eligible alternative.
    assert any(a["merchant"] == "TechHub" and a["eligible"] for a in alts.values())
    assert alts["Shady USB-C Hub"]["eligible"] is False
    assert "Merchant is on the allowlist" in alts["Shady USB-C Hub"]["blocking"]
    assert all(a["product_id"] != p["product_id"] for a in p["alternatives"])


def test_user_selected_alternative_goes_through_policy(client, sample_mandate, sample_product, db_session):
    bad = Product(name="Shady USB-C Hub", description="hub", price=Decimal("9.99"),
                  category="Electronics", merchant="UnknownSeller", in_stock=True)
    db_session.add(bad)
    db_session.commit()
    source = _gen(client, sample_mandate.id)["proposal"]

    res = client.post("/api/proposals/propose", json={
        "mandate_id": sample_mandate.id, "product_id": bad.id, "source_proposal_id": source["id"]})
    assert res.status_code == 201
    body = res.json()
    assert body["proposal"]["ai_provider"] == "user-selected"
    assert body["proposal"]["status"] == "POLICY_REJECTED"  # choosing it yourself does not bypass policy

    ok = client.post("/api/proposals/propose", json={"mandate_id": sample_mandate.id, "product_id": sample_product.id}).json()
    assert ok["proposal"]["status"] == "AWAITING_HUMAN_APPROVAL"
    assert client.post("/api/proposals/propose", json={"mandate_id": sample_mandate.id, "product_id": 424242}).status_code == 404
    assert client.post("/api/proposals/propose", json={
        "mandate_id": sample_mandate.id, "product_id": sample_product.id, "quantity": 500}).status_code == 422


# ---------------- receipt facts ----------------

def test_receipt_budget_impact_and_rule_facts(client, sample_mandate, sample_product):
    p = _gen(client, sample_mandate.id)["proposal"]
    r = client.get(f"/api/proposals/{p['id']}/receipt").json()
    assert r["product"]["id"] == sample_product.id
    b = r["budget"]
    assert Decimal(b["available"]) == Decimal("250.00")
    assert Decimal(b["this_purchase"]) == Decimal("34.99")
    assert Decimal(b["remaining_after"]) == Decimal("215.01")
    assert b["counted"] is False
    budget_rule = next(c for c in r["decision_checks"] if c["rule"] == "budget")
    assert budget_rule["actual"] == "$34.99" and "$250.00" in budget_rule["limit"]

    _approve(client, p)
    b2 = client.get(f"/api/proposals/{p['id']}/receipt").json()["budget"]
    assert b2["counted"] is True and Decimal(b2["remaining_after"]) == Decimal("215.01")


def test_blocked_receipt_shows_attempted_vs_allowed(client, sample_mandate, db_session):
    db_session.add(Product(name="Studio Display", description="monitor", price=Decimal("1599.00"),
                           category="Electronics", merchant="TechHub", in_stock=True))
    db_session.commit()
    p = _gen(client, sample_mandate.id, "studio display monitor")["proposal"]
    assert p["status"] == "POLICY_REJECTED"
    checks = {c["rule"]: c for c in p["policy_checks"]}
    assert checks["max_unit_price"]["actual"] == "$1,599.00"
    assert checks["max_unit_price"]["limit"] == "up to $150.00"
    assert checks["budget"]["passed"] is False
