"""Decimal money helpers. All amounts in PACT are Decimal, quantized to cents."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

CENT = Decimal("0.01")
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$", "JPY": "¥"}


def to_decimal(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """Convert any numeric-ish value to Decimal without float artifacts."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def q(value: Any) -> Decimal:
    """Quantize to two decimal places."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(value: Any, currency: str = "USD") -> str:
    """Human-readable money string, e.g. $99.99 or 99.99 SEK."""
    amount = q(value)
    symbol = _SYMBOLS.get(currency.upper())
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:,.2f} {currency.upper()}"


def paypal_value(value: Any) -> str:
    """PayPal Orders API amount string."""
    return f"{q(value):.2f}"
