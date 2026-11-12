"""Pytest fixtures for the PACT backend.

Tests never touch the real pact.db, never call OpenAI, and never call PayPal:
environment variables are pinned before the app is imported, and PayPal HTTP
calls are replaced by the FakePayPal fixture.
"""

import os

# Must run before any `app` import so Settings picks these up over backend/.env.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = ""
os.environ["CHANNEL3_API_KEY"] = ""
os.environ["PAYPAL_CLIENT_ID"] = "test-client-id"
os.environ["PAYPAL_CLIENT_SECRET"] = "test-client-secret"
os.environ["PAYPAL_BASE_URL"] = "https://api-m.sandbox.paypal.com"
os.environ["PAYPAL_CURRENCY"] = "USD"
os.environ["APP_BASE_URL"] = "http://testserver"
os.environ["FRONTEND_DIST"] = "/nonexistent-dist-for-tests"

from decimal import Decimal  # noqa: E402
from typing import Any, Dict, Generator, List, Optional  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import paypal as paypal_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Mandate, Product  # noqa: E402
from app.paypal import PayPalError  # noqa: E402
from app.routers import payments as payments_router  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_product(db_session: Session) -> Product:
    product = Product(
        name="Anker USB-C Hub",
        description="Multi-port USB-C adapter",
        price=Decimal("34.99"),
        category="Electronics",
        merchant="TechHub",
        image_url="https://example.com/anker.jpg",
        in_stock=True,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def sample_out_of_stock_product(db_session: Session) -> Product:
    product = Product(
        name="Keychron K2 Keyboard",
        description="Wireless mechanical keyboard",
        price=Decimal("79.99"),
        category="Electronics",
        merchant="TechHub",
        image_url="https://example.com/k2.jpg",
        in_stock=False,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def sample_mandate(db_session: Session) -> Mandate:
    mandate = Mandate(
        name="Developer Workstation Mandate",
        max_budget=Decimal("250.00"),
        currency="USD",
        allowed_merchants=["TechHub", "BookWorld"],
        allowed_categories=["Electronics", "Books"],
        restrictions={"max_price_per_item": 150.00},
        is_active=True,
    )
    db_session.add(mandate)
    db_session.commit()
    db_session.refresh(mandate)
    return mandate


# ---------------------------------------------------------------------------
# PayPal fake: replaces the three HTTP-calling functions used by the router.
# ---------------------------------------------------------------------------

class FakePayPal:
    """In-memory stand-in for PayPal Orders v2 with controllable behaviour."""

    def __init__(self) -> None:
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.create_calls = 0
        self.capture_calls = 0
        self.capture_request_ids: List[str] = []
        self.next_create_error: Optional[PayPalError] = None
        self.next_capture_error: Optional[PayPalError] = None
        self.capture_response_override: Optional[Dict[str, Any]] = None
        self.capture_status = "COMPLETED"
        self.capture_value_override: Optional[str] = None
        self._captured_by_request: Dict[str, Dict[str, Any]] = {}

    # --- helpers for tests ---
    def buyer_approves(self, order_id: str) -> None:
        self.orders[order_id]["status"] = "APPROVED"

    def order_for(self, proposal_id: str) -> Dict[str, Any]:
        return next(o for o in self.orders.values() if o["purchase_units"][0]["reference_id"] == proposal_id)

    # --- fakes ---
    async def create_order(self, **kw) -> Dict[str, Any]:
        self.create_calls += 1
        if self.next_create_error:
            err, self.next_create_error = self.next_create_error, None
            raise err
        order_id = f"5O190127TN{len(self.orders):06d}"
        self.orders[order_id] = {
            "id": order_id,
            "status": "PAYER_ACTION_REQUIRED",
            "purchase_units": [{
                "reference_id": kw["proposal_id"],
                "custom_id": kw["mandate_id"],
                "amount": {"currency_code": kw["currency"], "value": f"{Decimal(kw['total_amount']):.2f}"},
            }],
        }
        self.last_create_kwargs = kw
        return {
            "order_id": order_id,
            "status": "PAYER_ACTION_REQUIRED",
            "approve_url": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
        }

    async def get_order_details(self, order_id: str) -> Dict[str, Any]:
        if order_id not in self.orders:
            raise PayPalError("not found", code="RESOURCE_NOT_FOUND", status_code=404)
        import copy
        return copy.deepcopy(self.orders[order_id])

    async def capture_order(self, order_id: str, idempotency_key: str) -> Dict[str, Any]:
        self.capture_calls += 1
        request_id = f"cap-{idempotency_key}"
        self.capture_request_ids.append(request_id)
        if self.next_capture_error:
            err, self.next_capture_error = self.next_capture_error, None
            raise err
        if self.capture_response_override is not None:
            return self.capture_response_override
        if request_id in self._captured_by_request:  # PayPal idempotency semantics
            return self._captured_by_request[request_id]
        order = self.orders[order_id]
        if order["status"] != "APPROVED":
            raise PayPalError("not approved", code="ORDER_NOT_APPROVED", status_code=422, issues=["ORDER_NOT_APPROVED"])
        unit = order["purchase_units"][0]
        capture = {
            "id": f"3C679366HH{len(self._captured_by_request):06d}",
            "status": self.capture_status,
            "amount": {
                "currency_code": unit["amount"]["currency_code"],
                "value": self.capture_value_override or unit["amount"]["value"],
            },
        }
        if self.capture_status == "PENDING":
            capture["status_details"] = {"reason": "PENDING_REVIEW"}
        unit["payments"] = {"captures": [capture]}
        order["status"] = "COMPLETED"
        response = {"id": order_id, "status": "COMPLETED", "purchase_units": [unit]}
        self._captured_by_request[request_id] = response
        return response


@pytest.fixture
def fake_paypal(monkeypatch) -> FakePayPal:
    fake = FakePayPal()
    monkeypatch.setattr(payments_router, "create_order", fake.create_order)
    monkeypatch.setattr(payments_router, "get_order_details", fake.get_order_details)
    monkeypatch.setattr(payments_router, "capture_order", fake.capture_order)

    async def _no_network(*a, **k):  # safety net: any real PayPal HTTP call fails the test
        raise AssertionError("Real PayPal HTTP call attempted in tests")

    monkeypatch.setattr(paypal_module, "_request", _no_network)
    return fake


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch):
    """Every test: real PayPal HTTP and OpenAI calls are impossible."""
    async def _no_paypal(*a, **k):
        raise AssertionError("Real PayPal HTTP call attempted in tests")

    monkeypatch.setattr(paypal_module, "_request", _no_paypal)
    paypal_module._token_cache = (None, 0.0)
