"""Pytest test fixtures and configuration for PACT backend."""

from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Mandate, Product

# In-memory SQLite database for test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provide a pristine in-memory database session for each test function."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient configured with test database session override."""
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_product(db_session: Session) -> Product:
    """Fixture providing a standard in-stock product."""
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
    """Fixture providing an out-of-stock product."""
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
    """Fixture providing a standard spending mandate."""
    mandate = Mandate(
        name="Developer Workstation Mandate",
        max_budget=Decimal("250.00"),
        allowed_merchants=["TechHub", "BookWorld"],
        allowed_categories=["Electronics", "Books"],
        restrictions={"max_price_per_item": 150.00},
        is_active=True,
    )
    db_session.add(mandate)
    db_session.commit()
    db_session.refresh(mandate)
    return mandate
