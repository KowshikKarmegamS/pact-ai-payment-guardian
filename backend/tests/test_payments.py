"""Payment lifecycle tests: approval binding, order creation, buyer approval, verified capture.

All PayPal HTTP calls are replaced by FakePayPal (see conftest). Nothing here can
reach PayPal or charge anyone.
"""

import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AuditLog, Mandate, Product, Proposal, ProposalStatus
from app.paypal import PayPalError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _generate(client: TestClient, mandate_id: str, prompt: str = "USB-C hub adapter from TechHub") -> dict:
    res = client.post("/api/proposals/generate", json={"prompt": prompt, "mandate_id": mandate_id})
    assert res.status_code == 201, res.text
    return res.json()


def _approve(client: TestClient, proposal: dict) -> dict:
    res = client.post(f"/api/proposals/{proposal['id']}/approve",
                      json={"expected_fingerprint": proposal["proposal_fingerprint"]})
    assert res.status_code == 200, res.text
    return res.json()


def _approved_with_order(client, mandate_id, fake) -> dict:
    p = _generate(client, mandate_id)["proposal"]
    _approve(client, p)
    res = client.post(f"/api/payments/{p['id']}/create-order")
    assert res.status_code == 200, res.text
    return res.json()


def _events(db: Session, proposal_id: str):
    return [a.event_type for a in db.query(AuditLog).filter(AuditLog.entity_id == proposal_id).order_by(AuditLog.id)]


def _detail(res) -> dict:
    return res.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_full_lifecycle_captures_only_after_verified_paypal_response(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    gen = _generate(client, sample_mandate.id)
    proposal = gen["proposal"]
    assert proposal["status"] == "AWAITING_HUMAN_APPROVAL"
    assert len(proposal["proposal_fingerprint"]) == 64

    _approve(client, proposal)

    order = client.post(f"/api/payments/{proposal['id']}/create-order").json()
    assert order["proposal"]["status"] == "AWAITING_PAYPAL_BUYER_APPROVAL"
    assert order["approve_url"].startswith("https://www.sandbox.paypal.com/")
    # Return/cancel URLs come from APP_BASE_URL, not a hardcoded localhost.
    assert fake_paypal.last_create_kwargs["return_url"].startswith("http://testserver/assistant?paypal=return")
    assert fake_paypal.last_create_kwargs["cancel_url"].startswith("http://testserver/assistant?paypal=cancel")
    assert fake_paypal.last_create_kwargs["currency"] == "USD"

    fake_paypal.buyer_approves(order["order_id"])
    verify = client.post(f"/api/payments/{proposal['id']}/verify", json={"order_token": order["order_id"]})
    assert verify.status_code == 200
    assert verify.json()["proposal"]["status"] == "PAYPAL_BUYER_APPROVED"
    assert fake_paypal.capture_calls == 0, "verify must never capture"

    cap = client.post(f"/api/payments/{proposal['id']}/capture")
    assert cap.status_code == 200, cap.text
    body = cap.json()
    assert body["proposal"]["status"] == "CAPTURED"
    assert body["capture_status"] == "COMPLETED"
    assert body["paypal_order_status"] == "COMPLETED"
    assert body["capture_id"].startswith("3C679366HH")
    assert Decimal(body["proposal"]["captured_amount"]) == Decimal("34.99")

    events = _events(db_session, proposal["id"])
    for e in ["AI_RECOMMENDATION_GENERATED", "POLICY_CHECK_PASSED", "PROPOSAL_HUMAN_APPROVED",
              "PAYPAL_ORDER_CREATED", "PAYPAL_BUYER_APPROVED", "PAYPAL_CAPTURE_ATTEMPTED", "PAYPAL_PAYMENT_CAPTURED"]:
        assert e in events
    assert events.index("AI_RECOMMENDATION_GENERATED") < events.index("POLICY_CHECK_PASSED")

    mandate = client.get(f"/api/mandates/{sample_mandate.id}").json()
    assert Decimal(mandate["spent_budget"]) == Decimal("34.99")
    assert Decimal(mandate["committed_budget"]) == Decimal("0.00")


def test_budget_commitment_moves_from_committed_to_spent(client, sample_mandate, sample_product, fake_paypal):
    p = _generate(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    m = client.get(f"/api/mandates/{sample_mandate.id}").json()
    assert Decimal(m["committed_budget"]) == Decimal("34.99")
    assert Decimal(m["spent_budget"]) == Decimal("0.00")
    assert Decimal(m["remaining_budget"]) == Decimal("215.01")


# ---------------------------------------------------------------------------
# Capture safety
# ---------------------------------------------------------------------------

def test_capture_before_buyer_approval_is_refused(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert _detail(res)["code"] == "ORDER_NOT_APPROVED"
    assert fake_paypal.capture_calls == 0
    assert db_session.get(Proposal, pid).status == ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL
    assert "CAPTURE_BLOCKED_NOT_APPROVED" in _events(db_session, pid)


def test_capture_without_human_approval_is_refused(client, sample_mandate, sample_product, fake_paypal):
    p = _generate(client, sample_mandate.id)["proposal"]
    res = client.post(f"/api/payments/{p['id']}/capture")
    assert res.status_code == 409
    assert _detail(res)["code"] == "INVALID_STATE"
    res = client.post(f"/api/payments/{p['id']}/create-order")
    assert res.status_code == 409
    assert fake_paypal.create_calls == 0


def test_blocked_proposal_cannot_be_approved_or_ordered(client, sample_mandate, fake_paypal, db_session):
    ps5 = Product(name="Sony PlayStation 5", description="console", price=Decimal("499.99"),
                  category="Gaming Consoles", merchant="Sony Direct", in_stock=True)
    db_session.add(ps5)
    db_session.commit()
    gen = _generate(client, sample_mandate.id, "PlayStation 5 console")
    p = gen["proposal"]
    assert p["status"] == "POLICY_REJECTED"
    assert gen["policy"]["passed"] is False
    res = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": p["proposal_fingerprint"]})
    assert res.status_code == 409
    assert client.post(f"/api/payments/{p['id']}/create-order").status_code == 409
    assert fake_paypal.create_calls == 0


def test_repeated_capture_is_idempotent_and_calls_paypal_once(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])

    first = client.post(f"/api/payments/{pid}/capture").json()
    second = client.post(f"/api/payments/{pid}/capture")
    assert second.status_code == 200
    assert second.json()["capture_id"] == first["capture_id"]
    assert fake_paypal.capture_calls == 1
    assert "DUPLICATE_CAPTURE_PREVENTED" in _events(db_session, pid)


def test_concurrent_capture_is_rejected_while_lock_held(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])

    # Simulate another worker mid-capture.
    prop = db_session.get(Proposal, pid)
    prop.capture_lock_expires = time.time() + 30
    db_session.commit()

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert _detail(res)["code"] == "CAPTURE_IN_PROGRESS"
    assert fake_paypal.capture_calls == 0


def test_capture_uses_stable_paypal_request_id(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.next_capture_error = PayPalError("timeout", code="NETWORK_TIMEOUT")

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 504
    assert _detail(res)["retryable"] is True
    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.CAPTURE_PENDING
    assert prop.paypal_capture_id is None
    assert prop.capture_lock_expires is None, "lock must be released after failure"

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 200, res.text
    assert res.json()["proposal"]["status"] == "CAPTURED"
    # Both attempts used the same PayPal-Request-Id, so PayPal would dedupe them.
    assert len(set(fake_paypal.capture_request_ids)) == 1


def test_timeout_after_paypal_captured_reconciles_without_recapture(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])

    # PayPal captures, but our HTTP call times out.
    real_capture = fake_paypal.capture_order

    async def capture_then_timeout(order_id, key):
        await real_capture(order_id, key)
        raise PayPalError("timeout", code="NETWORK_TIMEOUT")

    fake_paypal.capture_order = capture_then_timeout
    import app.routers.payments as pr
    pr.capture_order = capture_then_timeout
    try:
        assert client.post(f"/api/payments/{pid}/capture").status_code == 504
    finally:
        pr.capture_order = real_capture

    calls_before = fake_paypal.capture_calls
    res = client.post(f"/api/payments/{pid}/verify")
    assert res.status_code == 200
    assert res.json()["proposal"]["status"] == "CAPTURED"
    assert fake_paypal.capture_calls == calls_before, "reconciliation must not capture again"


def test_missing_capture_id_is_not_reported_as_completed(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.capture_response_override = {"id": order["order_id"], "status": "COMPLETED", "purchase_units": [{}]}

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 502
    assert _detail(res)["code"] == "CAPTURE_UNVERIFIED"
    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.CAPTURE_PENDING
    assert prop.paypal_capture_id is None
    assert prop.status != ProposalStatus.CAPTURED


def test_pending_capture_is_not_marked_captured(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.capture_status = "PENDING"

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 200
    body = res.json()
    assert body["capture_status"] == "PENDING"
    assert body["proposal"]["status"] == "CAPTURE_PENDING"
    assert "PENDING_REVIEW" in body["message"]


def test_declined_capture_marks_payment_failed(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.capture_status = "DECLINED"

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 402
    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.PAYMENT_FAILED


def test_captured_amount_mismatch_is_flagged(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.capture_value_override = "1.00"

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 502
    assert _detail(res)["code"] == "CAPTURE_AMOUNT_MISMATCH"
    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.PAYMENT_FAILED
    assert "PAYPAL_CAPTURE_AMOUNT_MISMATCH" in _events(db_session, pid)


def test_paypal_order_amount_or_currency_mismatch_blocks_capture(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.orders[order["order_id"]]["purchase_units"][0]["amount"] = {"currency_code": "EUR", "value": "34.99"}

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert _detail(res)["code"] == "ORDER_MISMATCH"
    assert fake_paypal.capture_calls == 0


def test_order_for_a_different_proposal_blocks_capture(client, sample_mandate, sample_product, fake_paypal):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.orders[order["order_id"]]["purchase_units"][0]["reference_id"] = "someone-elses-proposal"
    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert fake_paypal.capture_calls == 0


def test_return_token_must_match_order(client, sample_mandate, sample_product, fake_paypal):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    res = client.post(f"/api/payments/{order['proposal']['id']}/verify", json={"order_token": "FORGEDTOKEN123"})
    assert res.status_code == 400
    assert _detail(res)["code"] == "ORDER_TOKEN_MISMATCH"


def test_verify_before_buyer_approval_reports_awaiting(client, sample_mandate, sample_product, fake_paypal):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    res = client.post(f"/api/payments/{order['proposal']['id']}/verify").json()
    assert res["proposal"]["status"] == "AWAITING_PAYPAL_BUYER_APPROVAL"
    assert "not approved" in res["message"]


# ---------------------------------------------------------------------------
# Approval binding
# ---------------------------------------------------------------------------

def test_approval_requires_matching_fingerprint(client, sample_mandate, sample_product, db_session):
    p = _generate(client, sample_mandate.id)["proposal"]
    res = client.post(f"/api/proposals/{p['id']}/approve", json={"expected_fingerprint": "0" * 64})
    assert res.status_code == 409
    assert _detail(res)["code"] == "FINGERPRINT_MISMATCH"
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.AWAITING_HUMAN_APPROVAL


def test_approval_without_body_is_rejected(client, sample_mandate, sample_product):
    p = _generate(client, sample_mandate.id)["proposal"]
    assert client.post(f"/api/proposals/{p['id']}/approve").status_code == 422


def test_mandate_change_after_approval_invalidates_and_blocks_capture(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])

    # The user tightens the mandate after approving.
    res = client.put(f"/api/mandates/{sample_mandate.id}", json={"allowed_merchants": ["BookWorld"]})
    assert res.status_code == 200

    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.APPROVAL_EXPIRED
    assert "Allowed merchants changed" in prop.status_reason

    cap = client.post(f"/api/payments/{pid}/capture")
    assert cap.status_code == 409
    assert fake_paypal.capture_calls == 0
    assert "APPROVAL_INVALIDATED" in _events(db_session, pid)


def test_pausing_mandate_invalidates_in_flight_approval(client, sample_mandate, sample_product, fake_paypal, db_session):
    p = _generate(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    client.put(f"/api/mandates/{sample_mandate.id}", json={"is_active": False})
    prop = db_session.get(Proposal, p["id"])
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.APPROVAL_EXPIRED
    assert client.post(f"/api/payments/{p['id']}/create-order").status_code == 409


def test_catalog_price_change_after_approval_blocks_capture(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    sample_product.price = Decimal("39.99")
    db_session.commit()

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert _detail(res)["code"] == "APPROVAL_INVALIDATED"
    assert "Catalog price changed" in _detail(res)["message"]
    assert fake_paypal.capture_calls == 0


def test_tampered_proposal_row_is_detected(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    prop = db_session.get(Proposal, pid)
    prop.quantity = 3
    prop.total_amount = Decimal("104.97")
    db_session.commit()

    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 409
    assert fake_paypal.capture_calls == 0


def test_re_evaluate_creates_fresh_proposal_requiring_new_approval(
    client, sample_mandate, sample_product, fake_paypal, db_session
):
    p = _generate(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    client.put(f"/api/mandates/{sample_mandate.id}", json={"max_budget": 300.00})
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.APPROVAL_EXPIRED

    res = client.post(f"/api/proposals/{p['id']}/re-evaluate")
    assert res.status_code == 201
    new = res.json()["proposal"]
    assert new["supersedes_id"] == p["id"]
    assert new["status"] == "AWAITING_HUMAN_APPROVAL"
    assert new["proposal_fingerprint"] != p["proposal_fingerprint"]


# ---------------------------------------------------------------------------
# Cancellation and errors
# ---------------------------------------------------------------------------

def test_buyer_cancel_then_reopen_reuses_order(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    res = client.post(f"/api/payments/{pid}/cancel").json()
    assert res["proposal"]["status"] == "PAYPAL_CANCELLED"
    assert client.post(f"/api/payments/{pid}/capture").status_code == 409

    reopened = client.post(f"/api/payments/{pid}/create-order").json()
    assert reopened["reused"] is True
    assert reopened["order_id"] == order["order_id"]
    assert fake_paypal.create_calls == 1


def test_create_order_is_idempotent(client, sample_mandate, sample_product, fake_paypal):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    again = client.post(f"/api/payments/{order['proposal']['id']}/create-order").json()
    assert again["order_id"] == order["order_id"]
    assert fake_paypal.create_calls == 1


@pytest.mark.parametrize("code,http", [
    ("CURRENCY_NOT_SUPPORTED", 422),
    ("MISSING_CREDENTIALS", 503),
    ("OAUTH_FAILED", 502),
    ("NETWORK_TIMEOUT", 504),
])
def test_order_creation_errors_are_reported_and_state_unchanged(
    client, sample_mandate, sample_product, fake_paypal, db_session, code, http
):
    p = _generate(client, sample_mandate.id)["proposal"]
    _approve(client, p)
    fake_paypal.next_create_error = PayPalError(f"{code} message", code=code)
    res = client.post(f"/api/payments/{p['id']}/create-order")
    assert res.status_code == http
    assert _detail(res)["code"] == code
    assert db_session.get(Proposal, p["id"]).status == ProposalStatus.HUMAN_APPROVED
    assert "PAYPAL_ORDER_FAILED" in _events(db_session, p["id"])


def test_capture_hard_failure_marks_failed_and_audits(client, sample_mandate, sample_product, fake_paypal, db_session):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    fake_paypal.buyer_approves(order["order_id"])
    fake_paypal.next_capture_error = PayPalError("unprocessable", code="UNPROCESSABLE", status_code=422)
    res = client.post(f"/api/payments/{pid}/capture")
    assert res.status_code == 502
    prop = db_session.get(Proposal, pid)
    db_session.refresh(prop)
    assert prop.status == ProposalStatus.PAYMENT_FAILED
    assert "PAYPAL_CAPTURE_FAILED" in _events(db_session, pid)


def test_receipt_explains_decision(client, sample_mandate, sample_product, fake_paypal):
    order = _approved_with_order(client, sample_mandate.id, fake_paypal)
    pid = order["proposal"]["id"]
    receipt = client.get(f"/api/proposals/{pid}/receipt").json()
    assert receipt["decision"] == "AUTHORIZED"
    rules = {c["rule"] for c in receipt["decision_checks"]}
    assert {"mandate_active", "merchant_allowlist", "category_allowlist", "budget", "max_unit_price"} <= rules
    assert all(c["passed"] for c in receipt["decision_checks"])
    assert receipt["integrity"]["intact"] is True
    assert receipt["integrity"]["approval_fingerprint"] == receipt["integrity"]["current_fingerprint"]
    assert receipt["proposal"]["paypal_capture_id"] is None
    types = [t["event_type"] for t in receipt["timeline"]]
    assert types[:2] == ["AI_RECOMMENDATION_GENERATED", "POLICY_CHECK_PASSED"]


def test_audit_never_stores_secrets(client, sample_mandate, sample_product, fake_paypal, db_session):
    _approved_with_order(client, sample_mandate.id, fake_paypal)
    blob = str([a.details for a in db_session.query(AuditLog).all()])
    assert "test-client-secret" not in blob
    assert "Bearer" not in blob
