"""Agent Gateway: any AI agent asks PACT for authority; it can request, never approve or pay."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import AgentClient, AuditLog, Mandate, Product, Proposal, ProposalStatus


@pytest.fixture
def pricey_product(db_session: Session) -> Product:
    p = Product(name="Pro Monitor Arm", description="Gas spring arm", price=Decimal("189.00"),
                category="Electronics", merchant="TechHub", in_stock=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def other_mandate(db_session: Session) -> Mandate:
    m = Mandate(name="Someone else's", max_budget=Decimal("50.00"), currency="USD",
                allowed_merchants=["TechHub"], allowed_categories=["Electronics"], restrictions={}, is_active=True)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


def _register(client: TestClient, mandate_ids, name="Claude Desktop (MCP)") -> dict:
    res = client.post("/api/agents", json={"name": name, "mandate_ids": mandate_ids})
    assert res.status_code == 201, res.text
    return res.json()


def _h(agent: dict) -> dict:
    return {"Authorization": f"Bearer {agent['api_key']}"}


def test_registration_returns_key_once_and_stores_only_its_hash(client, sample_mandate, db_session):
    agent = _register(client, [sample_mandate.id])
    assert agent["api_key"].startswith("pact_agent_")
    row = db_session.query(AgentClient).one()
    assert row.key_hash != agent["api_key"] and len(row.key_hash) == 64
    assert agent["api_key"] not in str(row.key_prefix)
    listed = client.get("/api/agents").json()
    assert "api_key" not in listed[0]
    logged = " ".join(str(a.details) for a in db_session.query(AuditLog).all())
    assert agent["api_key"] not in logged


def test_gateway_requires_a_valid_key(client, sample_mandate):
    assert client.get("/api/agent/v1/whoami").status_code == 401
    assert client.get("/api/agent/v1/whoami", headers={"Authorization": "Bearer pact_agent_nope"}).status_code == 401
    agent = _register(client, [sample_mandate.id])
    me = client.get("/api/agent/v1/whoami", headers=_h(agent))
    assert me.status_code == 200
    body = me.json()
    assert body["agent_name"] == "Claude Desktop (MCP)"
    assert body["mandates"][0]["remaining"] == "250.00"
    assert "approve a purchase" in body["cannot"]


def test_x_pact_agent_key_header_also_works(client, sample_mandate):
    agent = _register(client, [sample_mandate.id])
    assert client.get("/api/agent/v1/whoami", headers={"X-PACT-Agent-Key": agent["api_key"]}).status_code == 200


def test_revoked_agent_is_locked_out(client, sample_mandate):
    agent = _register(client, [sample_mandate.id])
    assert client.post(f"/api/agents/{agent['id']}/revoke").json()["status"] == "revoked"
    res = client.get("/api/agent/v1/whoami", headers=_h(agent))
    assert res.status_code == 401
    assert "revoked" in res.json()["detail"]["message"]


def test_agent_cannot_use_a_mandate_it_was_not_granted(client, sample_mandate, other_mandate, sample_product, db_session):
    agent = _register(client, [sample_mandate.id])
    res = client.post("/api/agent/v1/purchases", headers=_h(agent),
                      json={"mandate_id": other_mandate.id, "product_id": sample_product.id, "reason": "need it"})
    assert res.status_code == 403
    assert db_session.query(Proposal).count() == 0
    assert db_session.query(AuditLog).filter(AuditLog.event_type == "AGENT_MANDATE_DENIED").count() == 1


def test_over_limit_request_is_blocked_by_policy(client, sample_mandate, pricey_product):
    agent = _register(client, [sample_mandate.id])
    res = client.post("/api/agent/v1/purchases", headers=_h(agent),
                      json={"mandate_id": sample_mandate.id, "product_id": pricey_product.id, "reason": "nice arm"})
    assert res.status_code == 201
    body = res.json()
    assert body["decision"] == "BLOCKED" and body["status"] == "POLICY_REJECTED"
    assert any("189.00" in v for v in body["violations"])


def test_dry_run_creates_nothing(client, sample_mandate, sample_product, db_session):
    agent = _register(client, [sample_mandate.id])
    res = client.post("/api/agent/v1/purchases/evaluate", headers=_h(agent),
                      json={"mandate_id": sample_mandate.id, "product_id": sample_product.id, "quantity": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True and body["total"] == "69.98"
    assert db_session.query(Proposal).count() == 0


def test_agent_request_waits_for_human_and_records_the_agent(client, sample_mandate, sample_product, db_session):
    agent = _register(client, [sample_mandate.id])
    res = client.post("/api/agent/v1/purchases", headers=_h(agent),
                      json={"mandate_id": sample_mandate.id, "product_id": sample_product.id, "quantity": 1,
                            "reason": "User asked for a USB-C hub", "request_id": "req-1"})
    body = res.json()
    assert body["decision"] == "PENDING_HUMAN" and body["status"] == "AWAITING_HUMAN_APPROVAL"
    assert body["approval_url"].endswith(f"/proposals/{body['purchase_id']}")
    p = db_session.query(Proposal).one()
    assert p.agent_name == "Claude Desktop (MCP)" and p.price == Decimal("34.99")  # price from the catalog
    # The requesting agent is part of what the human approves.
    assert p.approval_snapshot["requested_by"]["agent_name"] == "Claude Desktop (MCP)"
    # Retrying with the same request_id does not create a second request.
    again = client.post("/api/agent/v1/purchases", headers=_h(agent),
                        json={"mandate_id": sample_mandate.id, "product_id": sample_product.id, "quantity": 1,
                              "reason": "retry", "request_id": "req-1"})
    assert again.json()["purchase_id"] == body["purchase_id"]
    assert db_session.query(Proposal).count() == 1


def test_gateway_exposes_no_approval_or_payment_route():
    paths = {path: ops for path, ops in app.openapi()["paths"].items() if path.startswith("/api/agent/")}
    assert "/api/agent/v1/purchases" in paths, "gateway routes missing"
    for path, ops in paths.items():
        for word in ("approve", "capture", "order", "payment", "revoke"):
            assert word not in path, path
        assert not set(ops) & {"put", "delete", "patch"}, path


def test_agent_sees_only_its_own_requests(client, sample_mandate, sample_product):
    a = _register(client, [sample_mandate.id], name="Agent A")
    b = _register(client, [sample_mandate.id], name="Agent B")
    made = client.post("/api/agent/v1/purchases", headers=_h(a),
                       json={"mandate_id": sample_mandate.id, "product_id": sample_product.id, "reason": "hub"}).json()
    assert client.get(f"/api/agent/v1/purchases/{made['purchase_id']}", headers=_h(b)).status_code == 404
    assert client.get("/api/agent/v1/purchases", headers=_h(b)).json() == []
    assert len(client.get("/api/agent/v1/purchases", headers=_h(a)).json()) == 1


def test_human_approval_then_status_reflects_it(client, sample_mandate, sample_product):
    agent = _register(client, [sample_mandate.id])
    made = client.post("/api/agent/v1/purchases", headers=_h(agent),
                       json={"mandate_id": sample_mandate.id, "product_id": sample_product.id, "reason": "hub"}).json()
    proposal = client.get(f"/api/proposals/{made['purchase_id']}").json()
    assert proposal["agent_name"] == "Claude Desktop (MCP)"
    res = client.post(f"/api/proposals/{proposal['id']}/approve",
                      json={"expected_fingerprint": proposal["proposal_fingerprint"]})
    assert res.status_code == 200
    status = client.get(f"/api/agent/v1/purchases/{made['purchase_id']}", headers=_h(agent)).json()
    assert status["status"] == "HUMAN_APPROVED" and status["paypal_capture_id"] is None


def test_catalog_search_ranks_matches(client, sample_mandate, sample_product, sample_out_of_stock_product):
    agent = _register(client, [sample_mandate.id])
    res = client.get("/api/agent/v1/catalog", params={"q": "usb-c hub"}, headers=_h(agent))
    assert res.status_code == 200
    assert res.json()[0]["product_id"] == sample_product.id
