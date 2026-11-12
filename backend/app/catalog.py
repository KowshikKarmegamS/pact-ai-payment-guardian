"""Default mandate seeding. Products come from merchant connectors (see app/connectors)."""

from decimal import Decimal
from sqlalchemy.orm import Session

SEED_MANDATES = [
    {
        # The demo video's mandate. Retailer domains as returned by Channel3 live search; any other retailer is blocked.
        # Purchases that pass every rule and cost at most $100 are auto-authorized; $100-$150 items need the owner.
        "name": "Desk tech (auto up to $100)",
        "max_budget": Decimal("400.00"),
        "allowed_merchants": ["newegg.com", "bestbuy.com", "keychron.com", "logitech.com", "anker.com"],
        "allowed_categories": ["Electronics"],
        "restrictions": {
            "max_price_per_item": 150.00,
            "max_quantity": 2,
        },
        "authorization_mode": "auto_approve_within_limits",
        "max_auto_approve_amount": Decimal("100.00"),
        "is_active": True,
    },
    {
        "name": "Q1 Developer Equipment & Workstation Peripherals",
        "max_budget": Decimal("750.00"),
        "allowed_merchants": ["TechHub", "BookWorld", "HomeEssentials", "MicroCenter", "GitHub"],
        "allowed_categories": ["Electronics", "Books", "Developer Tools"],
        "restrictions": {
            "max_price_per_item": 300.00,
            "prohibited_keywords": ["playstation", "xbox", "console", "game", "nintendo"],
            "prohibited_merchants": ["Sony Direct", "GameStop"],
        },
        "is_active": True,
    },
    {
        "name": "Engineering Books & Technical Learning",
        "max_budget": Decimal("250.00"),
        "allowed_merchants": ["BookWorld", "TechHub"],
        "allowed_categories": ["Books", "Electronics"],
        "restrictions": {
            "max_price_per_item": 75.00,
        },
        "is_active": True,
    },
]


def seed_mandates(db: Session):
    """Seed initial default mandates if none exist."""
    from app.config import get_settings
    from app.models import Mandate
    if db.query(Mandate).count() == 0:
        for m_data in SEED_MANDATES:
            mandate = Mandate(
                currency=get_settings().currency,
                name=m_data["name"],
                max_budget=m_data["max_budget"],
                allowed_merchants=m_data["allowed_merchants"],
                allowed_categories=m_data["allowed_categories"],
                restrictions=m_data["restrictions"],
                is_active=m_data["is_active"],
                authorization_mode=m_data.get("authorization_mode", "approval_required"),
                max_auto_approve_amount=m_data.get("max_auto_approve_amount"),
            )
            db.add(mandate)
        db.commit()
