"""Unit tests for the PACT PolicyEngine evaluated strictly in isolation without database."""

from decimal import Decimal
import pytest
from app.policy import PolicyEngine, evaluate_policy


@pytest.fixture
def policy_engine() -> PolicyEngine:
    """Fixture providing a clean PolicyEngine instance."""
    return PolicyEngine()


@pytest.fixture
def base_mandate() -> dict:
    """Standard authorized mandate configuration."""
    return {
        "id": "mandate-123",
        "name": "Engineering Supplies",
        "max_budget": Decimal("200.00"),
        "allowed_merchants": ["TechHub", "BookWorld"],
        "allowed_categories": ["Electronics", "Books"],
        "restrictions": {
            "max_price_per_item": 100.00,
            "max_quantity": 5,
            "prohibited_keywords": ["gambling", "crypto", "weapon"],
        },
        "is_active": True,
    }


def test_valid_proposal_passes(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that a compliant proposal successfully passes all policy checks."""
    proposal = {
        "product_name": "USB-C Hub",
        "merchant": "TechHub",
        "category": "Electronics",
        "price": Decimal("35.00"),
        "quantity": 1,
        "total_amount": Decimal("35.00"),
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is True
    assert len(result.violations) == 0


def test_merchant_not_allowed(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that a merchant outside the allowed list is blocked."""
    proposal = {
        "product_name": "Running Shoes",
        "merchant": "SportZone",  # Not in ["TechHub", "BookWorld"]
        "category": "Electronics",
        "price": Decimal("50.00"),
        "quantity": 1,
        "total_amount": Decimal("50.00"),
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is False
    assert any("Merchant 'SportZone' is not permitted" in v for v in result.violations)


def test_category_not_allowed(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that a category outside the allowed list is blocked."""
    proposal = {
        "product_name": "Desk Chair",
        "merchant": "TechHub",
        "category": "Furniture",  # Not in ["Electronics", "Books"]
        "price": Decimal("80.00"),
        "quantity": 1,
        "total_amount": Decimal("80.00"),
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is False
    assert any("Category 'Furniture' is not permitted" in v for v in result.violations)


def test_budget_exceeded(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that an order total exceeding remaining budget is rejected."""
    proposal = {
        "product_name": "Premium Keyboard",
        "merchant": "TechHub",
        "category": "Electronics",
        "price": Decimal("90.00"),
        "quantity": 3,
        "total_amount": Decimal("270.00"),  # Exceeds max_budget of 200.00
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is False
    assert any("exceeds remaining mandate budget" in v for v in result.violations)


def test_budget_exceeded_with_custom_remaining_budget(
    policy_engine: PolicyEngine,
    base_mandate: dict,
) -> None:
    """Verify that explicit remaining_budget parameter is enforced."""
    proposal = {
        "product_name": "Technical Book",
        "merchant": "BookWorld",
        "category": "Books",
        "price": Decimal("40.00"),
        "quantity": 1,
        "total_amount": Decimal("40.00"),
        "in_stock": True,
    }

    # Only $25.00 left on mandate
    result = policy_engine.evaluate(
        mandate=base_mandate,
        proposal=proposal,
        remaining_budget=Decimal("25.00"),
    )

    assert result.passed is False
    assert any("exceeds remaining mandate budget of $25.00" in v for v in result.violations)


def test_out_of_stock_product(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that out of stock products trigger a policy violation."""
    proposal = {
        "product_name": "Out of Stock Adapter",
        "merchant": "TechHub",
        "category": "Electronics",
        "price": Decimal("25.00"),
        "quantity": 1,
        "total_amount": Decimal("25.00"),
        "in_stock": False,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is False
    assert any("is currently out of stock" in v for v in result.violations)


def test_multiple_violations(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that ALL violations are detected and aggregated when multiple rules fail."""
    proposal = {
        "product_name": "Crypto Miner Pro",  # Contains prohibited keyword "crypto"
        "merchant": "UnapprovedShadyShop",   # Invalid merchant
        "category": "GamblingSupplies",      # Invalid category & prohibited keyword
        "price": Decimal("500.00"),          # Exceeds max item price & budget
        "quantity": 10,                      # Exceeds max quantity (5)
        "total_amount": Decimal("5000.00"),  # Exceeds budget
        "in_stock": False,                   # Out of stock
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)

    assert result.passed is False
    # Check that each violation type was recorded
    assert any("Merchant 'UnapprovedShadyShop' is not permitted" in v for v in result.violations)
    assert any("Category 'GamblingSupplies' is not permitted" in v for v in result.violations)
    assert any("exceeds remaining mandate budget" in v for v in result.violations)
    assert any("is currently out of stock" in v for v in result.violations)
    assert any("exceeds maximum allowed limit" in v for v in result.violations)
    assert any("exceeds maximum allowed quantity" in v for v in result.violations)
    assert any("prohibited keyword: 'crypto'" in v for v in result.violations)
    assert len(result.violations) >= 5


def test_inactive_mandate(policy_engine: PolicyEngine, base_mandate: dict) -> None:
    """Verify that an inactive mandate disallows transactions."""
    inactive_mandate = dict(base_mandate)
    inactive_mandate["is_active"] = False

    proposal = {
        "product_name": "USB-C Cable",
        "merchant": "TechHub",
        "category": "Electronics",
        "price": Decimal("15.00"),
        "quantity": 1,
        "total_amount": Decimal("15.00"),
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=inactive_mandate, proposal=proposal)

    assert result.passed is False
    assert any("Mandate is inactive" in v for v in result.violations)


def test_case_insensitive_merchant_and_category(
    policy_engine: PolicyEngine,
    base_mandate: dict,
) -> None:
    """Verify merchant and category whitelist checking is properly case-insensitive."""
    proposal = {
        "product_name": "USB-C Cable",
        "merchant": "techhub",       # Lowercase match for "TechHub"
        "category": "electronics",   # Lowercase match for "Electronics"
        "price": Decimal("15.00"),
        "quantity": 1,
        "total_amount": Decimal("15.00"),
        "in_stock": True,
    }

    result = policy_engine.evaluate(mandate=base_mandate, proposal=proposal)
    assert result.passed is True


def test_helper_evaluate_policy_function(base_mandate: dict) -> None:
    """Verify the evaluate_policy module function works identically to the class method."""
    proposal = {
        "product_name": "Python Book",
        "merchant": "BookWorld",
        "category": "Books",
        "price": Decimal("30.00"),
        "quantity": 1,
        "total_amount": Decimal("30.00"),
        "in_stock": True,
    }

    result = evaluate_policy(mandate=base_mandate, proposal=proposal)
    assert result.passed is True
    assert len(result.violations) == 0
