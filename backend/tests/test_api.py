"""Integration tests for PACT FastAPI endpoints."""

from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import AuditLog, Mandate, Product


def test_health_endpoint(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.2.0"
    assert "timestamp" in data


def test_root_endpoint(client: TestClient) -> None:
    """Test root service information endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["service"] == "PACT – AI Payment Authorization Gateway"


def test_products_list_and_filter(
    client: TestClient,
    sample_product: Product,
    sample_out_of_stock_product: Product,
) -> None:
    """Test listing products and filtering by category, merchant, and in_stock."""
    # List all
    response = client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 2

    # Filter by category
    response = client.get("/api/products?category=Electronics")
    assert response.status_code == 200
    assert all(p["category"] == "Electronics" for p in response.json())

    # Filter by stock
    response = client.get("/api/products?in_stock=false")
    assert response.status_code == 200
    filtered = response.json()
    assert len(filtered) >= 1
    assert all(p["in_stock"] is False for p in filtered)


def test_get_single_product(client: TestClient, sample_product: Product) -> None:
    """Test retrieving a single product by ID."""
    response = client.get(f"/api/products/{sample_product.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_product.id
    assert data["name"] == sample_product.name
    assert Decimal(str(data["price"])) == sample_product.price

    # Non-existent product
    not_found = client.get("/api/products/999999")
    assert not_found.status_code == 404


def test_mandate_lifecycle(client: TestClient, db_session: Session) -> None:
    """Test creating, listing, getting, and updating a spending mandate."""
    create_payload = {
        "name": "Hardware Lab Budget",
        "max_budget": 500.00,
        "allowed_merchants": ["TechHub", "MicroCenter"],
        "allowed_categories": ["Electronics"],
        "restrictions": {"max_price_per_item": 200.00},
    }

    # 1. Create mandate
    create_res = client.post("/api/mandates", json=create_payload)
    assert create_res.status_code == 201
    mandate_data = create_res.json()
    mandate_id = mandate_data["id"]
    assert mandate_data["name"] == "Hardware Lab Budget"
    assert Decimal(str(mandate_data["max_budget"])) == Decimal("500.00")
    assert Decimal(str(mandate_data["remaining_budget"])) == Decimal("500.00")
    assert Decimal(str(mandate_data["spent_budget"])) == Decimal("0.00")

    # Verify audit log was created
    audit = db_session.query(AuditLog).filter(AuditLog.entity_id == mandate_id).first()
    assert audit is not None
    assert audit.event_type == "MANDATE_CREATED"

    # 2. Get mandate
    get_res = client.get(f"/api/mandates/{mandate_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == mandate_id

    # 3. List mandates
    list_res = client.get("/api/mandates")
    assert list_res.status_code == 200
    all_mandates = list_res.json()
    assert any(m["id"] == mandate_id for m in all_mandates)

    # 4. Update mandate
    update_res = client.put(
        f"/api/mandates/{mandate_id}",
        json={"max_budget": 750.00, "is_active": False},
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert Decimal(str(updated_data["max_budget"])) == Decimal("750.00")
    assert updated_data["is_active"] is False

    # Non-existent mandate
    not_found = client.get("/api/mandates/non-existent-id")
    assert not_found.status_code == 404


def test_proposal_generation_and_approval_workflow(
    client: TestClient,
    sample_mandate: Mandate,
    sample_product: Product,
    db_session: Session,
) -> None:
    """Test full Guardian flow: AI generation -> Policy check -> Human approval."""
    # 1. Generate Proposal via AI shopping request
    gen_payload = {
        "prompt": "Find me high performance wireless headphones from TechHub",
        "mandate_id": sample_mandate.id,
    }
    gen_res = client.post("/api/proposals/generate", json=gen_payload)
    assert gen_res.status_code == 201
    data = gen_res.json()
    proposal = data["proposal"]
    policy = data["policy"]

    assert policy["passed"] is True
    assert proposal["status"] == "AWAITING_HUMAN_APPROVAL"
    assert data["ai"]["provider"] == "heuristic"
    assert data["ai"]["fallback_reason"]
    assert proposal["product_id"] == sample_product.id
    assert proposal["merchant"] == sample_product.merchant
    proposal_id = proposal["id"]

    # 2. Human approval of proposal
    approve_res = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={"expected_fingerprint": proposal["proposal_fingerprint"]},
    )
    assert approve_res.status_code == 200
    approved_proposal = approve_res.json()
    assert approved_proposal["status"] == "HUMAN_APPROVED"
    assert approved_proposal["approval_fingerprint"] == proposal["proposal_fingerprint"]
    assert approved_proposal["approved_at"]

    # 3. Verify audit log captures both events
    audit_events = client.get("/api/audit").json()
    assert any(a["event_type"] == "POLICY_CHECK_PASSED" for a in audit_events)
    assert any(a["event_type"] == "PROPOSAL_HUMAN_APPROVED" for a in audit_events)


def test_proposal_blocked_by_policy_engine(
    client: TestClient,
    sample_mandate: Mandate,
    sample_out_of_stock_product: Product,
) -> None:
    """Test that a proposal violating mandate policy is blocked and marked rejected."""
    # Temporarily set mandate budget to a tiny amount to trigger violation
    client.put(f"/api/mandates/{sample_mandate.id}", json={"max_budget": 5.00})

    gen_payload = {
        "prompt": "Buy headphones",
        "mandate_id": sample_mandate.id,
    }
    gen_res = client.post("/api/proposals/generate", json=gen_payload)
    assert gen_res.status_code == 201
    data = gen_res.json()
    proposal = data["proposal"]
    policy = data["policy"]

    # Must be blocked by policy engine
    assert policy["passed"] is False
    assert len(policy["violations"]) > 0
    assert proposal["status"] == "POLICY_REJECTED"

