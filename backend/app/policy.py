"""Deterministic policy evaluation engine for payment proposals.

This module is the sole authorization authority in PACT. It is pure: no database,
no network, no AI. Given a mandate and a proposal it returns the same decision
every time, with a per-rule explanation that powers the Authorization Receipt.

AI-produced text (reasoning, product descriptions) is never an input here.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.money import fmt, q, to_decimal
from app.schemas import PolicyCheck, PolicyResult

# Hard ceiling regardless of mandate: an agent may never order more than this.
MAX_QUANTITY_HARD_LIMIT = 20


def _val(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


class PolicyEngine:
    """Pure, side-effect-free policy engine for validating purchase proposals."""

    @staticmethod
    def evaluate(
        mandate: Any,
        proposal: Any,
        remaining_budget: Optional[Decimal] = None,
        product: Optional[Any] = None,
        expected_currency: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> PolicyResult:
        """Evaluate every rule and collect all results (no short-circuit).

        Args:
            mandate: Mandate ORM object, schema or dict.
            proposal: Proposal ORM object, schema or dict.
            remaining_budget: Budget available to *this* proposal. If omitted,
                mandate.remaining_budget or mandate.max_budget is used.
            product: Catalog product for stock checks (falls back to proposal.product).
            expected_currency: The configured system currency.
        """
        checks: List[PolicyCheck] = []

        def add(rule: str, label: str, passed: bool, detail: str) -> None:
            checks.append(PolicyCheck(rule=rule, label=label, passed=passed, detail=detail))

        currency = str(_val(mandate, "currency", None) or expected_currency or "USD").upper()
        p_currency = str(_val(proposal, "currency", None) or currency).upper()

        # 1. Mandate active
        is_active = bool(_val(mandate, "is_active", True))
        add(
            "mandate_active",
            "Mandate is active",
            is_active,
            "Mandate is active." if is_active else "Mandate is inactive.",
        )

        # 1b. Mandate expiry (only when the user set one)
        expires_at = _val(mandate, "expires_at", None)
        if isinstance(expires_at, datetime):
            exp = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at
            current = now or datetime.now(timezone.utc)
            current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current
            not_expired = current < exp
            stamp = exp.strftime("%Y-%m-%d %H:%M UTC")
            add(
                "mandate_not_expired",
                "Mandate has not expired",
                not_expired,
                f"Mandate is valid until {stamp}." if not_expired else f"Mandate expired on {stamp}.",
            )

        p_merchant = str(_val(proposal, "merchant", "") or "").strip()
        p_category = str(_val(proposal, "category", "") or "").strip()
        p_name = str(_val(proposal, "product_name", "") or "Unknown Product").strip()
        raw_qty = _val(proposal, "quantity", 1)
        try:
            p_qty = int(raw_qty)
        except (TypeError, ValueError):
            p_qty = 0
        p_price = q(_val(proposal, "price", "0"))
        raw_total = _val(proposal, "total_amount", None)
        p_total = q(raw_total) if raw_total is not None else q(p_price * Decimal(max(p_qty, 0)))

        # 2. Currency consistency
        currency_ok = p_currency == currency and (expected_currency is None or currency == expected_currency.upper())
        add(
            "currency",
            "Currency matches mandate",
            currency_ok,
            f"Proposal currency {p_currency} matches mandate currency {currency}."
            if currency_ok
            else f"Currency mismatch: proposal is {p_currency}, mandate is {currency}"
            + (f", system is {expected_currency.upper()}." if expected_currency else "."),
        )

        # 3. Quantity bounds
        restrictions = _val(mandate, "restrictions", {}) or {}
        if not isinstance(restrictions, dict):
            restrictions = {}
        max_qty_raw = restrictions.get("max_quantity")
        max_qty = MAX_QUANTITY_HARD_LIMIT
        if max_qty_raw is not None:
            try:
                max_qty = min(int(max_qty_raw), MAX_QUANTITY_HARD_LIMIT)
            except (TypeError, ValueError):
                pass
        qty_ok = isinstance(raw_qty, int) and not isinstance(raw_qty, bool) and 1 <= p_qty <= max_qty
        add(
            "quantity",
            "Quantity within limits",
            qty_ok,
            f"Quantity {p_qty} is within the allowed range 1–{max_qty}."
            if qty_ok
            else (
                f"Quantity {raw_qty} exceeds maximum allowed quantity of {max_qty}."
                if p_qty > max_qty
                else f"Quantity {raw_qty} is invalid; it must be a whole number from 1 to {max_qty}."
            ),
        )

        # 4. Amount integrity (total must equal unit price x quantity, and be positive)
        expected_total = q(p_price * Decimal(max(p_qty, 0)))
        amount_ok = p_price > 0 and p_total > 0 and p_total == expected_total
        add(
            "amount_integrity",
            "Total equals price × quantity",
            amount_ok,
            f"{fmt(p_price, currency)} × {p_qty} = {fmt(p_total, currency)}."
            if amount_ok
            else f"Amount inconsistency: {fmt(p_price, currency)} × {p_qty} = {fmt(expected_total, currency)}, "
            f"but proposal total is {fmt(p_total, currency)}.",
        )

        # 5. Merchant allowlist
        allowed_merchants = _clean_list(_val(mandate, "allowed_merchants", []))
        merchant_ok = bool(p_merchant) and p_merchant.lower() in {m.lower() for m in allowed_merchants}
        add(
            "merchant_allowlist",
            "Merchant is on the allowlist",
            merchant_ok,
            f"Merchant '{p_merchant}' is on the allowlist."
            if merchant_ok
            else f"Merchant '{p_merchant}' is not permitted by mandate. Allowed: [{', '.join(allowed_merchants) or 'None'}].",
        )

        # 6. Merchant blocklist
        blocked_merchants = _clean_list(restrictions.get("prohibited_merchants", []))
        if blocked_merchants:
            blocked = p_merchant.lower() in {m.lower() for m in blocked_merchants}
            add(
                "merchant_blocklist",
                "Merchant is not blocked",
                not blocked,
                f"Merchant '{p_merchant}' is explicitly blocked by mandate restrictions."
                if blocked
                else f"Merchant '{p_merchant}' is not on the blocklist.",
            )

        # 7. Category allowlist
        allowed_categories = _clean_list(_val(mandate, "allowed_categories", []))
        category_ok = bool(p_category) and p_category.lower() in {c.lower() for c in allowed_categories}
        add(
            "category_allowlist",
            "Category is on the allowlist",
            category_ok,
            f"Category '{p_category}' is on the allowlist."
            if category_ok
            else f"Category '{p_category}' is not permitted by mandate. Allowed: [{', '.join(allowed_categories) or 'None'}].",
        )

        # 8. Max unit price
        max_item = restrictions.get("max_price_per_item", restrictions.get("max_item_price"))
        if max_item is not None:
            max_item_dec = q(max_item)
            ok = p_price <= max_item_dec
            add(
                "max_unit_price",
                "Unit price within limit",
                ok,
                f"Unit price {fmt(p_price, currency)} is within the {fmt(max_item_dec, currency)} limit."
                if ok
                else f"Item unit price {fmt(p_price, currency)} exceeds maximum allowed limit of {fmt(max_item_dec, currency)}.",
            )

        # 9. Min unit price
        min_item = restrictions.get("min_price_per_item", restrictions.get("min_item_price"))
        if min_item is not None:
            min_item_dec = q(min_item)
            ok = p_price >= min_item_dec
            add(
                "min_unit_price",
                "Unit price above minimum",
                ok,
                f"Unit price {fmt(p_price, currency)} meets the {fmt(min_item_dec, currency)} minimum."
                if ok
                else f"Item unit price {fmt(p_price, currency)} is below minimum allowed limit of {fmt(min_item_dec, currency)}.",
            )

        # 10. Prohibited keywords (product name and category; never AI text)
        keywords = _clean_list(restrictions.get("prohibited_keywords", []))
        if keywords:
            haystack = f"{p_name} {p_category}".lower()
            hits = [kw for kw in keywords if kw.lower() in haystack]
            add(
                "prohibited_keywords",
                "No prohibited keywords",
                not hits,
                "No prohibited keywords found in product name or category."
                if not hits
                else " ".join(f"Product contains prohibited keyword: '{h}'." for h in hits),
            )

        # 11. Budget
        if remaining_budget is not None:
            budget = q(remaining_budget)
        else:
            rem = _val(mandate, "remaining_budget", None)
            budget = q(rem) if rem is not None else q(_val(mandate, "max_budget", "0"))
        budget_ok = p_total <= budget
        add(
            "budget",
            "Within available budget",
            budget_ok,
            f"Total {fmt(p_total, currency)} fits within the remaining budget of {fmt(budget, currency)}."
            if budget_ok
            else f"Total amount {fmt(p_total, currency)} exceeds remaining mandate budget of {fmt(budget, currency)}.",
        )

        # 12. Stock
        stock_src = product if product is not None else _val(proposal, "product", None)
        in_stock = bool(_val(stock_src, "in_stock", True)) if stock_src is not None else bool(_val(proposal, "in_stock", True))
        add(
            "in_stock",
            "Product is in stock",
            in_stock,
            f"'{p_name}' is in stock." if in_stock else f"Product '{p_name}' is currently out of stock.",
        )

        # Attach "what the proposal has" vs "what the mandate allows" for the authorization screen.
        scope = locals()
        facts: Dict[str, tuple] = {
            "merchant_allowlist": (p_merchant or "none", ", ".join(allowed_merchants) or "none"),
            "category_allowlist": (p_category or "none", ", ".join(allowed_categories) or "none"),
            "budget": (fmt(p_total, currency), f"{fmt(budget, currency)} available"),
            "quantity": (str(raw_qty), f"1 to {max_qty}"),
            "amount_integrity": (fmt(p_total, currency), fmt(expected_total, currency)),
            "currency": (p_currency, currency),
        }
        if "max_item_dec" in scope:
            facts["max_unit_price"] = (fmt(p_price, currency), f"up to {fmt(scope['max_item_dec'], currency)}")
        if "min_item_dec" in scope:
            facts["min_unit_price"] = (fmt(p_price, currency), f"at least {fmt(scope['min_item_dec'], currency)}")
        if blocked_merchants:
            facts["merchant_blocklist"] = (p_merchant or "none", "not " + ", ".join(blocked_merchants))
        if keywords:
            facts["prohibited_keywords"] = (p_name, "must not contain " + ", ".join(keywords))
        for c in checks:
            if c.rule in facts:
                c.actual, c.limit = facts[c.rule]

        violations = [c.detail for c in checks if not c.passed]
        return PolicyResult(
            passed=not violations,
            violations=violations,
            checks=checks,
            remaining_budget=budget,
            currency=currency,
        )


policy_engine = PolicyEngine()


def evaluate_policy(
    mandate: Any,
    proposal: Any,
    remaining_budget: Optional[Decimal] = None,
    product: Optional[Any] = None,
    expected_currency: Optional[str] = None,
    now: Optional[datetime] = None,
) -> PolicyResult:
    """Evaluate a proposal against mandate policies using the global PolicyEngine."""
    return policy_engine.evaluate(
        mandate=mandate,
        proposal=proposal,
        remaining_budget=remaining_budget,
        product=product,
        expected_currency=expected_currency,
        now=now,
    )


def checks_to_json(result: PolicyResult) -> List[Dict[str, Any]]:
    return [c.model_dump() for c in result.checks]


__all__ = ["PolicyEngine", "evaluate_policy", "checks_to_json", "MAX_QUANTITY_HARD_LIMIT", "to_decimal"]
