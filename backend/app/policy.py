"""Deterministic policy evaluation engine for payment proposals.

Enforces spending mandates, merchant whitelists, category restrictions,
budget constraints, stock availability, and fine-grained purchase restrictions.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional
from app.schemas import PolicyResult


def _extract_val(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extract an attribute or dictionary key from an object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_decimal(val: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """Safely convert any numeric value to Decimal."""
    if val is None:
        return default
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return default


class PolicyEngine:
    """Pure, side-effect-free policy engine for validating purchase proposals."""

    @staticmethod
    def evaluate(
        mandate: Any,
        proposal: Any,
        remaining_budget: Optional[Decimal] = None,
        product: Optional[Any] = None,
    ) -> PolicyResult:
        """Evaluate a proposal against mandate policies.

        All rules are evaluated deterministically and all violations are collected.

        Checks performed:
        1. Is mandate active?
        2. Is merchant in allowed_merchants?
        3. Is category in allowed_categories?
        4. Is total_amount <= remaining budget?
        5. Is product in stock?
        6. Does it violate any fine-grained restrictions?

        Args:
            mandate: Mandate ORM object, Pydantic schema, or dict.
            proposal: Proposal ORM object, Pydantic schema, or dict.
            remaining_budget: Optional remaining budget; if omitted, checks
                              mandate.remaining_budget or mandate.max_budget.
            product: Optional Product object; if omitted, checks proposal.product
                     or proposal.in_stock.

        Returns:
            PolicyResult indicating pass/fail status and all violations found.
        """
        violations: List[str] = []

        # ---------------------------------------------------------------------
        # 1. Mandate Active Check
        # ---------------------------------------------------------------------
        is_active = _extract_val(mandate, "is_active", True)
        if not is_active:
            violations.append("Mandate is inactive.")

        # ---------------------------------------------------------------------
        # Extract proposal attributes
        # ---------------------------------------------------------------------
        p_merchant = str(_extract_val(proposal, "merchant", "")).strip()
        p_category = str(_extract_val(proposal, "category", "")).strip()
        p_product_name = str(_extract_val(proposal, "product_name", "Unknown Product")).strip()
        p_quantity = int(_extract_val(proposal, "quantity", 1))

        # Price and total amount resolution
        p_price = _to_decimal(_extract_val(proposal, "price", Decimal("0.00")))
        p_total = _extract_val(proposal, "total_amount", None)
        if p_total is not None:
            p_total_amount = _to_decimal(p_total)
        else:
            p_total_amount = p_price * Decimal(p_quantity)

        # ---------------------------------------------------------------------
        # 2. Merchant Whitelist Check
        # ---------------------------------------------------------------------
        allowed_merchants = _extract_val(mandate, "allowed_merchants", []) or []
        allowed_merchants_clean = [str(m).strip() for m in allowed_merchants if str(m).strip()]
        allowed_merchants_lower = [m.lower() for m in allowed_merchants_clean]

        if not p_merchant or p_merchant.lower() not in allowed_merchants_lower:
            allowed_str = ", ".join(allowed_merchants_clean) if allowed_merchants_clean else "None"
            violations.append(
                f"Merchant '{p_merchant}' is not permitted by mandate. Allowed: [{allowed_str}]."
            )

        # ---------------------------------------------------------------------
        # 3. Category Whitelist Check
        # ---------------------------------------------------------------------
        allowed_categories = _extract_val(mandate, "allowed_categories", []) or []
        allowed_categories_clean = [str(c).strip() for c in allowed_categories if str(c).strip()]
        allowed_categories_lower = [c.lower() for c in allowed_categories_clean]

        if not p_category or p_category.lower() not in allowed_categories_lower:
            allowed_str = ", ".join(allowed_categories_clean) if allowed_categories_clean else "None"
            violations.append(
                f"Category '{p_category}' is not permitted by mandate. Allowed: [{allowed_str}]."
            )

        # ---------------------------------------------------------------------
        # 4. Budget Constraint Check
        # ---------------------------------------------------------------------
        if remaining_budget is not None:
            effective_budget = _to_decimal(remaining_budget)
        else:
            mandate_rem = _extract_val(mandate, "remaining_budget", None)
            if mandate_rem is not None:
                effective_budget = _to_decimal(mandate_rem)
            else:
                effective_budget = _to_decimal(_extract_val(mandate, "max_budget", Decimal("0.00")))

        if p_total_amount > effective_budget:
            violations.append(
                f"Total amount ${p_total_amount:.2f} exceeds remaining mandate budget of ${effective_budget:.2f}."
            )

        # ---------------------------------------------------------------------
        # 5. Stock Availability Check
        # ---------------------------------------------------------------------
        # Priority order: explicitly passed product -> proposal.product -> proposal.in_stock
        stock_status = True
        if product is not None:
            stock_status = bool(_extract_val(product, "in_stock", True))
        else:
            nested_product = _extract_val(proposal, "product", None)
            if nested_product is not None:
                stock_status = bool(_extract_val(nested_product, "in_stock", True))
            else:
                stock_status = bool(_extract_val(proposal, "in_stock", True))

        if not stock_status:
            violations.append(f"Product '{p_product_name}' is currently out of stock.")

        # ---------------------------------------------------------------------
        # 6. Fine-grained Restrictions Check
        # ---------------------------------------------------------------------
        restrictions = _extract_val(mandate, "restrictions", {}) or {}
        if isinstance(restrictions, dict):
            # Maximum price per item
            max_item_price = restrictions.get("max_price_per_item") or restrictions.get("max_item_price")
            if max_item_price is not None:
                max_price_dec = _to_decimal(max_item_price)
                if p_price > max_price_dec:
                    violations.append(
                        f"Item unit price ${p_price:.2f} exceeds maximum allowed limit of ${max_price_dec:.2f}."
                    )

            # Minimum price per item
            min_item_price = restrictions.get("min_price_per_item") or restrictions.get("min_item_price")
            if min_item_price is not None:
                min_price_dec = _to_decimal(min_item_price)
                if p_price < min_price_dec:
                    violations.append(
                        f"Item unit price ${p_price:.2f} is below minimum allowed limit of ${min_price_dec:.2f}."
                    )

            # Maximum quantity limit
            max_qty = restrictions.get("max_quantity")
            if max_qty is not None and p_quantity > int(max_qty):
                violations.append(
                    f"Quantity {p_quantity} exceeds maximum allowed quantity of {max_qty}."
                )

            # Prohibited keywords in product name
            prohibited_keywords = restrictions.get("prohibited_keywords", [])
            if isinstance(prohibited_keywords, list):
                name_lower = p_product_name.lower()
                for kw in prohibited_keywords:
                    kw_clean = str(kw).strip().lower()
                    if kw_clean and kw_clean in name_lower:
                        violations.append(
                            f"Product name contains prohibited keyword: '{kw}'."
                        )

            # Prohibited merchants
            prohibited_merchants = restrictions.get("prohibited_merchants", [])
            if isinstance(prohibited_merchants, list):
                prohibited_lower = [str(m).strip().lower() for m in prohibited_merchants]
                if p_merchant.lower() in prohibited_lower:
                    violations.append(
                        f"Merchant '{p_merchant}' is explicitly blocked by mandate restrictions."
                    )

        passed = len(violations) == 0
        return PolicyResult(passed=passed, violations=violations)


# Convenient module-level singleton instance and function
policy_engine = PolicyEngine()


def evaluate_policy(
    mandate: Any,
    proposal: Any,
    remaining_budget: Optional[Decimal] = None,
    product: Optional[Any] = None,
) -> PolicyResult:
    """Evaluate a proposal against mandate policies using the global PolicyEngine."""
    return policy_engine.evaluate(
        mandate=mandate,
        proposal=proposal,
        remaining_budget=remaining_budget,
        product=product,
    )
