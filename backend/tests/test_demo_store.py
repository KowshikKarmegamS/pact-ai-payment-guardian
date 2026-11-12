"""The Demo Store connector: deterministic offers loaded through the same connector path as Channel3."""

from decimal import Decimal

from app.connectors import get_connector
from app.connectors.demo_store import SEED_PRODUCTS, slug
from app.models import Product
from app.services.connector_sync import seed_demo_store


def test_seeding_goes_through_the_connector_and_is_idempotent(db_session):
    seed_demo_store(db_session)
    rows = db_session.query(Product).all()
    assert len(rows) == len(SEED_PRODUCTS)
    assert {p.source for p in rows} == {"demo-store"}
    k8 = next(p for p in rows if p.name.startswith("Keychron K8 Pro"))
    assert k8.price == Decimal("89.00") and k8.merchant == "TechHub" and k8.external_id == slug(k8.name)
    k8.price = Decimal("99.50")  # an owner's demo price change survives restarts
    db_session.commit()
    seed_demo_store(db_session)
    assert db_session.query(Product).count() == len(SEED_PRODUCTS)
    assert db_session.get(Product, k8.id).price == Decimal("99.50")


def test_legacy_builtin_rows_are_attributed_to_the_demo_store(db_session):
    db_session.add(Product(name="Old Hub", description="", price=Decimal("10.00"), category="Electronics",
                           merchant="TechHub", in_stock=True, source="pact-catalog"))
    db_session.commit()
    seed_demo_store(db_session)
    old = db_session.query(Product).filter(Product.name == "Old Hub").one()
    assert old.source == "demo-store" and old.external_id == "old-hub"
    assert db_session.query(Product).count() == 1  # existing store data is not duplicated


def test_demo_store_is_a_listed_syncable_connector(client, db_session):
    listed = {c["id"]: c for c in client.get("/api/connectors").json()}
    assert listed["demo-store"]["syncable"] and not listed["demo-store"]["searchable"]
    res = client.post("/api/connectors/demo-store/sync")
    assert res.status_code == 200 and res.json()["created"] == len(SEED_PRODUCTS)
    assert get_connector("demo-store").fetch_offers()[0].currency == "USD"


def test_reference_agent_demo_mode_only_offers_demo_store_items(client, db_session, sample_mandate, sample_product):
    db_session.add(Product(name="USB-C hub adapter from a live retailer", description="usb-c hub adapter",
                           price=Decimal("20.00"), category="Electronics", merchant="TechHub", in_stock=True,
                           source="channel3", external_id="x:techhub", purchase_url="https://buy.trychannel3.com/x"))
    db_session.commit()
    res = client.post("/api/proposals/generate", json={"prompt": "USB-C hub adapter", "mandate_id": sample_mandate.id,
                                                        "source": "demo-store"})
    assert res.status_code == 201 and res.json()["proposal"]["product_id"] == sample_product.id
