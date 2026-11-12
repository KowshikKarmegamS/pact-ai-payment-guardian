"""Auto-authorization within limits, exception approval, hard blocks, and atomic budget reservation."""

import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AuditLog, Mandate, Product, Proposal, ProposalStatus, utc_now
from app.paypal import PayPalError
from app.routers.proposals import _create_and_evaluate
from app.services.mandate_service import budget_breakdown


def _mandate(db, **kw):
    m = Mandate(name=kw.pop("name", "Desk gear"), max_budget=kw.pop("max_budget", Decimal("200.00")), currency="USD",
                allowed_merchants=["TechHub"], allowed_categories=["Electronics"],
                restrictions=kw.pop("restrictions", {"max_price_per_item": 150.00, "max_quantity": 2}),
                is_active=True, **kw)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def auto_mandate(db_session):
    return _mandate(db_session, authorization_mode="auto_approve_within_limits", max_auto_approve_amount=Decimal("100.00"))


def _propose(client, mandate, product, quantity=1):
    res = client.post("/api/proposals/propose", json={"mandate_id": mandate.id, "product_id": product.id, "quantity": quantity})
    assert res.status_code == 201, res.text
    return res.json()["proposal"]


def _events(db, pid):
    return [a.event_type for a in db.query(AuditLog).filter(AuditLog.entity_id == pid).order_by(AuditLog.id)]


# ------------------------------------------------------------------------------------------- the three outcomes

def test_auto_approve_within_limit_still_needs_paypal_buyer_approval(client, db_session, auto_mandate, sample_product, fake_paypal):
    p = _propose(client, auto_mandate, sample_product)
    assert p["status"] == "AUTO_AUTHORIZED" and p["authorization_decision"] == "AUTO_APPROVE"
    assert p["authorized_by"] == "mandate" and p["approval_fingerprint"] == p["proposal_fingerprint"]
    assert "within your $100.00 auto-authorization limit" in p["decision_reason"]
    _, committed, remaining = budget_breakdown(db_session, auto_mandate)
    assert committed == Decimal("34.99") and remaining == Decimal("165.01")

    # No extra human approval exists for it, and none is needed.
    assert client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]}).status_code == 409

    order = client.post(f"/api/payments/{p['id']}/create-order")
    assert order.status_code == 200, order.text
    # PACT authorization is not PayPal consent: capture is refused until PayPal reports the buyer's approval.
    refused = client.post(f"/api/payments/{p['id']}/capture")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "ORDER_NOT_APPROVED"
    assert fake_paypal.capture_calls == 0
    fake_paypal.buyer_approves(order.json()["order_id"])
    cap = client.post(f"/api/payments/{p['id']}/capture")
    assert cap.status_code == 200 and cap.json()["proposal"]["status"] == "CAPTURED"
    again = client.post(f"/api/payments/{p['id']}/capture")
    assert again.status_code == 200 and fake_paypal.capture_calls == 1  # duplicate capture prevented

    decided = db_session.query(AuditLog).filter(AuditLog.entity_id == p["id"], AuditLog.event_type == "AUTHORIZATION_DECIDED").one()
    d = decided.details
    assert d["decision"] == "AUTO_APPROVE" and d["mandate_id"] == auto_mandate.id
    assert d["budget_reservation"] == f"rsv-{p['id'][:8]}" and d["fingerprint"] == p["proposal_fingerprint"]
    assert d["payment_status"] == "NOT_STARTED"


def test_existing_mandates_keep_approval_required(client, db_session, sample_mandate, sample_product):
    assert sample_mandate.authorization_mode == "approval_required"
    out = client.get(f"/api/mandates/{sample_mandate.id}").json()
    assert out["authorization_mode"] == "approval_required" and out["max_auto_approve_amount"] is None
    p = _propose(client, sample_mandate, sample_product)
    assert p["status"] == "AWAITING_HUMAN_APPROVAL" and p["authorization_decision"] == "REQUIRES_APPROVAL"
    assert "requires your approval for every purchase" in p["decision_reason"]
    _, committed, _ = budget_breakdown(db_session, sample_mandate)
    assert committed == Decimal("0.00")  # pending approval reserves nothing


def test_above_auto_limit_escalates_and_owner_approval_binds_the_exact_purchase(client, db_session, sample_product):
    m = _mandate(db_session, authorization_mode="auto_approve_within_limits", max_auto_approve_amount=Decimal("30.00"))
    p = _propose(client, m, sample_product)  # $34.99 > $30.00 limit, every rule passes
    assert p["status"] == "AWAITING_HUMAN_APPROVAL" and p["authorization_decision"] == "REQUIRES_APPROVAL"
    assert "above your $30.00 auto-authorization limit" in p["decision_reason"]
    ok = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    assert ok.status_code == 200 and ok.json()["status"] == "HUMAN_APPROVED" and ok.json()["authorized_by"] == "owner"


@pytest.mark.parametrize("restrictions,expect", [
    ({"prohibited_merchants": ["TechHub"]}, "explicitly blocked"),
    ({"prohibited_keywords": ["usb"]}, "keyword"),
    ({"max_price_per_item": 20.0}, "exceeds maximum"),
])
def test_hard_violations_are_blocked_without_an_approval_override(client, db_session, sample_product, restrictions, expect):
    m = _mandate(db_session, restrictions=restrictions, authorization_mode="auto_approve_within_limits",
                 max_auto_approve_amount=Decimal("100.00"))
    p = _propose(client, m, sample_product)
    assert p["status"] == "POLICY_REJECTED" and p["authorization_decision"] == "BLOCKED"
    assert expect in p["decision_reason"].lower()
    assert client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]}).status_code == 409
    assert client.post(f"/api/payments/{p['id']}/create-order").status_code == 409


def test_over_auto_limit_with_hard_violations_is_blocked_not_escalated(client, db_session, auto_mandate):
    # The demo's third outcome: an offer above the auto limit that also breaks hard rules (merchant, item cap, budget)
    # must be BLOCKED with every violation listed, never offered for owner approval as a mere escalation.
    offer = Product(name="Wireless Mouse", description="", price=Decimal("544.95"), category="Electronics",
                    merchant="6ave.com", in_stock=True)
    db_session.add(offer)
    db_session.commit()
    p = _propose(client, auto_mandate, offer)
    assert p["status"] == "POLICY_REJECTED" and p["authorization_decision"] == "BLOCKED"
    failed = {c["rule"] for c in p["policy_checks"] if not c["passed"]}
    assert {"merchant_allowlist", "max_unit_price", "budget"} <= failed
    assert "auto-authorization limit" not in p["decision_reason"]
    assert client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]}).status_code == 409
    assert client.post(f"/api/payments/{p['id']}/create-order").status_code == 409


def test_expired_mandate_and_revoked_agent_are_blocked(client, db_session, auto_mandate, sample_product):
    agent = client.post("/api/agents", json={"name": "Shopper", "mandate_ids": [auto_mandate.id]}).json()
    h = {"Authorization": f"Bearer {agent['api_key']}"}
    body = {"mandate_id": auto_mandate.id, "product_id": sample_product.id, "reason": "needs a hub"}

    auto_mandate.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()
    res = client.post("/api/agent/v1/purchases", headers=h, json=body).json()
    assert res["decision"] == "BLOCKED" and res["authorization_decision"] == "BLOCKED" and res["payment_status"] == "NOT_STARTED"

    auto_mandate.expires_at = None
    db_session.commit()
    client.post(f"/api/agents/{agent['id']}/revoke")
    before = db_session.query(Proposal).count()
    assert client.post("/api/agent/v1/purchases", headers=h, json=body).status_code == 401
    assert db_session.query(Proposal).count() == before


def test_agent_sees_authorization_separately_from_payment(client, db_session, auto_mandate, sample_product):
    agent = client.post("/api/agents", json={"name": "Shopper", "mandate_ids": [auto_mandate.id]}).json()
    h = {"Authorization": f"Bearer {agent['api_key']}"}
    res = client.post("/api/agent/v1/purchases", headers=h, json={
        "mandate_id": auto_mandate.id, "product_id": sample_product.id, "reason": "needs a hub"}).json()
    assert res["status"] == "AUTO_AUTHORIZED" and res["decision"] == "AUTHORIZED"
    assert res["payment_status"] == "NOT_STARTED" and res["paypal_capture_id"] is None
    assert "NOT payment" in res["next_step"]
    # Agents have no way to approve or pay: those routes do not exist on the gateway.
    for path in (f"/api/agent/v1/purchases/{res['purchase_id']}/approve", f"/api/agent/v1/purchases/{res['purchase_id']}/capture"):
        assert client.post(path, headers=h).status_code in (404, 405)


# ------------------------------------------------------------------------------------------- integrity

def test_price_change_after_auto_authorization_stops_execution(client, db_session, auto_mandate, sample_product, fake_paypal):
    p = _propose(client, auto_mandate, sample_product)
    client.put(f"/api/products/{sample_product.id}", json={"price": "36.00"})
    db_session.expire_all()
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.APPROVAL_EXPIRED
    assert client.post(f"/api/payments/{p['id']}/create-order").status_code == 409
    assert fake_paypal.create_calls == 0
    _, committed, _ = budget_breakdown(db_session, auto_mandate)
    assert committed == Decimal("0.00")  # voided purchase released its reservation


def test_lowering_the_auto_limit_voids_purchases_authorized_under_it(client, db_session, auto_mandate, sample_product):
    p = _propose(client, auto_mandate, sample_product)
    res = client.put(f"/api/mandates/{auto_mandate.id}", json={"max_auto_approve_amount": "20.00"})
    assert res.status_code == 200
    db_session.expire_all()
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.APPROVAL_EXPIRED


def test_stale_fingerprint_cannot_be_reused(client, db_session, sample_mandate, sample_product):
    p = _propose(client, sample_mandate, sample_product)
    client.put(f"/api/products/{sample_product.id}", json={"price": "30.00"})
    res = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    assert res.status_code == 409


def test_mandate_auto_terms_are_validated(client):
    base = {"name": "M", "max_budget": "100.00", "allowed_merchants": ["TechHub"], "allowed_categories": ["Electronics"]}
    assert client.post("/api/mandates", json={**base, "authorization_mode": "auto_approve_within_limits"}).status_code == 422
    assert client.post("/api/mandates", json={**base, "authorization_mode": "auto_approve_within_limits",
                                              "max_auto_approve_amount": "150.00"}).status_code == 422
    ok = client.post("/api/mandates", json={**base, "authorization_mode": "auto_approve_within_limits",
                                            "max_auto_approve_amount": "50.00"})
    assert ok.status_code == 201 and ok.json()["max_auto_approve_amount"] == "50.00"
    assert client.put(f"/api/mandates/{ok.json()['id']}", json={"max_budget": "40.00"}).status_code == 422


# ------------------------------------------------------------------------------------------- reservations

def test_reservation_released_on_definitive_failure_kept_on_uncertain_outcome(client, db_session, sample_product, fake_paypal):
    m = _mandate(db_session, authorization_mode="auto_approve_within_limits", max_auto_approve_amount=Decimal("100.00"))
    a = _propose(client, m, sample_product)
    order = client.post(f"/api/payments/{a['id']}/create-order").json()
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.next_capture_error = PayPalError("timeout", code="NETWORK_TIMEOUT")
    assert client.post(f"/api/payments/{a['id']}/capture").status_code >= 500
    db_session.expire_all()
    assert db_session.get(Proposal, a["id"]).status == ProposalStatus.CAPTURE_PENDING
    _, committed, _ = budget_breakdown(db_session, m)
    assert committed == Decimal("34.99")  # PayPal may have captured: the reservation stays

    b = _propose(client, m, sample_product)
    order = client.post(f"/api/payments/{b['id']}/create-order").json()
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.next_capture_error = PayPalError("unprocessable", code="UNPROCESSABLE", status_code=422)
    client.post(f"/api/payments/{b['id']}/capture")
    db_session.expire_all()
    assert db_session.get(Proposal, b["id"]).status == ProposalStatus.PAYMENT_FAILED
    _, committed, _ = budget_breakdown(db_session, m)
    assert committed == Decimal("34.99")  # only the uncertain one still holds budget

    c = _propose(client, m, sample_product)
    client.post(f"/api/proposals/{c['id']}/reject")
    _, committed, _ = budget_breakdown(db_session, m)
    assert committed == Decimal("34.99")


def test_concurrent_auto_authorizations_cannot_overspend(tmp_path):
    """Eight agents ask at the same moment for a $34.99 item under a $100 budget: at most two fit."""
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as s:
        m = Mandate(name="Tight", max_budget=Decimal("100.00"), currency="USD", allowed_merchants=["TechHub"],
                    allowed_categories=["Electronics"], restrictions={}, is_active=True,
                    authorization_mode="auto_approve_within_limits", max_auto_approve_amount=Decimal("100.00"))
        prod = Product(name="Hub", description="usb-c hub", price=Decimal("34.99"), category="Electronics",
                       merchant="TechHub", in_stock=True)
        s.add_all([m, prod])
        s.commit()
        mid, pid = m.id, prod.id

    barrier = threading.Barrier(8)
    errors = []

    def worker():
        with Session() as s:
            mandate, product = s.get(Mandate, mid), s.get(Product, pid)
            barrier.wait()
            try:
                _create_and_evaluate(s, mandate, product, 1, prompt=None, reasoning="race", provider="test",
                                     model=None, fallback_reason=None)
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    with Session() as s:
        statuses = [p.status for p in s.query(Proposal).all()]
        assert len(statuses) == 8
        assert statuses.count(ProposalStatus.AUTO_AUTHORIZED) == 2
        assert statuses.count(ProposalStatus.POLICY_REJECTED) == 6
        spent, committed, remaining = budget_breakdown(s, s.get(Mandate, mid))
        assert committed == Decimal("69.98") and remaining == Decimal("30.02")
    engine.dispose()


def test_concurrent_owner_approvals_cannot_overspend(tmp_path, monkeypatch):
    """Two $60 approvals race for a $100 budget. The budget read is slowed down so both overlap."""
    import time
    from fastapi import HTTPException
    from app.routers.proposals import approve_proposal
    from app.schemas import ProposalApproval
    from app.services import authorization as authz

    real = authz.budget_breakdown

    def slow_breakdown(*a, **k):
        out = real(*a, **k)
        time.sleep(0.3)
        return out

    monkeypatch.setattr(authz, "budget_breakdown", slow_breakdown)
    engine = create_engine(f"sqlite:///{tmp_path / 'race2.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as s:
        m = Mandate(name="Tight", max_budget=Decimal("100.00"), currency="USD", allowed_merchants=["TechHub"],
                    allowed_categories=["Electronics"], restrictions={}, is_active=True)
        prod = Product(name="Arm", description="monitor arm", price=Decimal("60.00"), category="Electronics",
                       merchant="TechHub", in_stock=True)
        s.add_all([m, prod])
        s.commit()
        mid = m.id
        ids = []
        for _ in range(2):
            p, _ = _create_and_evaluate(s, m, prod, 1, prompt=None, reasoning="x", provider="test", model=None, fallback_reason=None)
            assert p.status == ProposalStatus.AWAITING_HUMAN_APPROVAL
            ids.append((p.id, p.proposal_fingerprint))

    barrier = threading.Barrier(2)
    results = []

    def approve(pid, fp):
        with Session() as s:
            barrier.wait()
            try:
                approve_proposal(pid, ProposalApproval(expected_fingerprint=fp), s)
                results.append("approved")
            except HTTPException as exc:
                results.append(exc.detail["code"])

    threads = [threading.Thread(target=approve, args=x) for x in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["APPROVAL_INVALIDATED", "approved"], results
    with Session() as s:
        _, committed, remaining = budget_breakdown(s, s.get(Mandate, mid))
        assert committed == Decimal("60.00") and remaining == Decimal("40.00")
    engine.dispose()


def test_analytics_shows_how_each_purchase_was_authorized(client, db_session, auto_mandate, sample_product, sample_out_of_stock_product):
    m = _mandate(db_session, name="Strict")
    _propose(client, auto_mandate, sample_product)              # auto
    _propose(client, m, sample_product)                         # needs owner
    _propose(client, auto_mandate, sample_out_of_stock_product)  # blocked (out of stock)
    rows = client.get("/api/analytics/dataset").json()["purchases"]
    assert sorted(r["authorization"] for r in rows) == ["Auto-authorized", "Blocked", "Needed owner approval"]
    auto = next(r for r in rows if r["authorization"] == "Auto-authorized")
    assert auto["authorized_amount"] == 34.99 and auto["paid_amount"] == 0.0
    assert all(r["authorized_amount"] == 0.0 for r in rows if r["authorization"] != "Auto-authorized")


def test_fresh_database_seeds_the_demo_videos_auto_authorization_mandate(db_session):
    from app.catalog import seed_mandates

    seed_mandates(db_session)
    m = db_session.query(Mandate).filter(Mandate.name == "Desk tech (auto up to $100)").one()
    assert m.authorization_mode == "auto_approve_within_limits" and m.max_auto_approve_amount == Decimal("100.00")
    assert m.restrictions["max_price_per_item"] == 150.0 and m.max_budget == Decimal("400.00")
    assert set(m.allowed_merchants) == {"newegg.com", "bestbuy.com", "keychron.com", "logitech.com", "anker.com"}
    others = db_session.query(Mandate).filter(Mandate.id != m.id).all()
    assert others and all(o.authorization_mode == "approval_required" for o in others)
