"""PayPal REST API integration (Sandbox only).

Implements:
1. OAuth 2.0 client-credentials token management
2. Orders API v2: create order, get order, capture order
3. Idempotency via the PayPal-Request-Id header
4. Error classification with sanitized diagnostics

Never logs or returns access tokens, client secrets, authorization headers or raw
payloads. Only PayPal's issue codes and debug_id are surfaced.
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import get_settings
from app.money import paypal_value

logger = logging.getLogger("pact.paypal")

# In-memory token cache (access_token, expiration_epoch_seconds)
_token_cache: Tuple[Optional[str], float] = (None, 0.0)


class PayPalError(Exception):
    """PayPal integration error with a stable machine-readable code.

    code values:
      CONFIG_NOT_SANDBOX, MISSING_CREDENTIALS, OAUTH_FAILED, NETWORK_TIMEOUT,
      NETWORK_ERROR, CURRENCY_NOT_SUPPORTED, ORDER_NOT_APPROVED,
      ORDER_ALREADY_CAPTURED, INSTRUMENT_DECLINED, PAYER_ACTION_REQUIRED,
      RESOURCE_NOT_FOUND, UNPROCESSABLE, SERVER_ERROR, API_ERROR
    """

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        status_code: Optional[int] = None,
        issues: Optional[List[str]] = None,
        debug_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.issues = issues or []
        self.debug_id = debug_id

    @property
    def retryable(self) -> bool:
        return self.code in {"NETWORK_TIMEOUT", "NETWORK_ERROR", "SERVER_ERROR"}

    def safe_details(self) -> Dict[str, Any]:
        """Sanitized diagnostic dict for logs, audit and API responses."""
        return {
            "code": self.code,
            "http_status": self.status_code,
            "issues": self.issues,
            "debug_id": self.debug_id,
        }


_FRIENDLY = {
    "CURRENCY_NOT_SUPPORTED": (
        "PayPal rejected the currency {currency}. The Sandbox seller account must be able to "
        "receive {currency}. Either enable {currency} on the seller account or set PAYPAL_CURRENCY "
        "to a currency it accepts. PACT never converts or switches currency automatically."
    ),
    "ORDER_NOT_APPROVED": "The buyer has not approved this order in PayPal Checkout yet.",
    "ORDER_ALREADY_CAPTURED": "PayPal reports this order has already been captured.",
    "INSTRUMENT_DECLINED": (
        "The buyer's funding source was declined. The buyer can reopen PayPal Checkout and choose another one."
    ),
    "PAYER_ACTION_REQUIRED": "PayPal requires further buyer action before capture.",
}


def _settings():
    return get_settings()


def _ensure_sandbox() -> str:
    s = _settings()
    if not s.paypal_is_sandbox:
        raise PayPalError(
            "PAYPAL_BASE_URL must be a PayPal Sandbox endpoint (https://api-m.sandbox.paypal.com). "
            "PACT refuses to contact production PayPal.",
            code="CONFIG_NOT_SANDBOX",
        )
    return s.PAYPAL_BASE_URL.strip().rstrip("/")


def _parse_error(response: httpx.Response, context: str) -> PayPalError:
    issues: List[str] = []
    name = None
    debug_id = None
    try:
        body = response.json()
        name = body.get("name") or body.get("error")
        debug_id = body.get("debug_id")
        for d in body.get("details", []) or []:
            if isinstance(d, dict) and d.get("issue"):
                issues.append(str(d["issue"]))
    except Exception:  # non-JSON error body
        pass

    code = "API_ERROR"
    for issue in issues:
        if issue in _FRIENDLY or issue == "CURRENCY_NOT_SUPPORTED_FOR_RECEIVER":
            code = "CURRENCY_NOT_SUPPORTED" if issue.startswith("CURRENCY_NOT_SUPPORTED") else issue
            break
    else:
        if response.status_code == 404:
            code = "RESOURCE_NOT_FOUND"
        elif response.status_code >= 500:
            code = "SERVER_ERROR"
        elif response.status_code == 422:
            code = "UNPROCESSABLE"

    currency = _settings().currency
    friendly = _FRIENDLY.get(code, "").format(currency=currency)
    message = friendly or f"PayPal {context} failed (HTTP {response.status_code}{', ' + name if name else ''})."
    err = PayPalError(message, code=code, status_code=response.status_code, issues=issues, debug_id=debug_id)
    logger.warning("PayPal %s error: %s", context, err.safe_details())
    return err


async def _request(method: str, path: str, *, context: str, headers: Dict[str, str], **kwargs) -> httpx.Response:
    base_url = _ensure_sandbox()
    timeout = httpx.Timeout(_settings().PAYPAL_TIMEOUT_SECONDS, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(method, f"{base_url}{path}", headers=headers, **kwargs)
    except httpx.TimeoutException:
        logger.warning("PayPal %s timed out", context)
        raise PayPalError(
            f"PayPal {context} timed out. The outcome is unknown; it is safe to retry (requests are idempotent).",
            code="NETWORK_TIMEOUT",
        )
    except httpx.HTTPError as exc:
        logger.warning("PayPal %s network error: %s", context, type(exc).__name__)
        raise PayPalError(f"Could not reach PayPal for {context} ({type(exc).__name__}).", code="NETWORK_ERROR")


async def get_access_token(force_refresh: bool = False) -> str:
    """Retrieve or refresh a PayPal OAuth2 access token using client credentials."""
    global _token_cache
    now = time.time()
    cached_token, expiry = _token_cache
    if cached_token and not force_refresh and now < (expiry - 60):
        return cached_token

    s = _settings()
    _ensure_sandbox()
    if not s.paypal_credentials_configured:
        raise PayPalError(
            "PayPal Sandbox credentials are missing. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in backend/.env.",
            code="MISSING_CREDENTIALS",
        )

    response = await _request(
        "POST",
        "/v1/oauth2/token",
        context="OAuth token request",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=(s.PAYPAL_CLIENT_ID.strip(), s.PAYPAL_CLIENT_SECRET.strip()),
    )
    if response.status_code != 200:
        # Do not parse/log the body beyond the error name.
        try:
            err_name = response.json().get("error")
        except Exception:
            err_name = None
        logger.warning("PayPal OAuth failed: HTTP %s (%s)", response.status_code, err_name)
        raise PayPalError(
            "PayPal OAuth failed. Check that PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are Sandbox REST app credentials"
            + (f" (PayPal: {err_name})." if err_name else "."),
            code="OAUTH_FAILED",
            status_code=response.status_code,
        )

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise PayPalError("PayPal OAuth response did not include an access token.", code="OAUTH_FAILED")
    _token_cache = (token, now + float(data.get("expires_in", 3600)))
    logger.info("Acquired PayPal Sandbox OAuth token")
    return token


# Orders v2 defaults to "Prefer: return=minimal" (id, status and links only; see the PayPal Server SDK's
# OrdersController docs). PACT verifies captures from purchase_units[].payments.captures, so it always asks
# for the full representation instead of relying on PayPal returning more than the documented minimum.
PREFER_FULL = "return=representation"


async def _authed(method: str, path: str, context: str, request_id: Optional[str] = None,
                  prefer: Optional[str] = None, **kwargs) -> httpx.Response:
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    if prefer:
        headers["Prefer"] = prefer
    response = await _request(method, path, context=context, headers=headers, **kwargs)
    if response.status_code == 401:
        # Token revoked/expired early: refresh once.
        token = await get_access_token(force_refresh=True)
        headers["Authorization"] = f"Bearer {token}"
        response = await _request(method, path, context=context, headers=headers, **kwargs)
    return response


# purchase_units[].description: content beyond 127 characters is truncated by PayPal (PayPal Server SDK
# PurchaseUnitRequest docs), so PACT cuts it itself and controls what the buyer sees.
DESCRIPTION_MAX = 127


def order_description(product_name: str, merchant: str) -> str:
    prefix, joiner = "PACT authorized purchase: ", " from "
    store = merchant.strip()[:40]
    room = DESCRIPTION_MAX - len(prefix) - len(joiner) - len(store)
    name = product_name.strip()
    if len(name) > room:
        name = name[: max(room - 1, 1)].rstrip() + "…"
    return f"{prefix}{name}{joiner}{store}"[:DESCRIPTION_MAX]


def _approve_link(data: Dict[str, Any]) -> Optional[str]:
    for link in data.get("links", []) or []:
        if link.get("rel") in ("approve", "payer-action"):
            return link.get("href")
    return None


async def create_order(
    proposal_id: str,
    product_name: str,
    merchant: str,
    total_amount: Decimal,
    price: Decimal,
    quantity: int,
    mandate_id: str,
    idempotency_key: str,
    currency: str,
    return_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a PayPal v2 order whose amount and item exactly match the approved proposal."""
    total = paypal_value(total_amount)
    unit = paypal_value(price)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(proposal_id),
                "custom_id": str(mandate_id),
                "description": order_description(product_name, merchant),
                "amount": {
                    "currency_code": currency,
                    "value": total,
                    "breakdown": {"item_total": {"currency_code": currency, "value": total}},
                },
                "items": [
                    {
                        "name": product_name[:127],
                        "unit_amount": {"currency_code": currency, "value": unit},
                        "quantity": str(int(quantity)),
                        "category": "PHYSICAL_GOODS",
                    }
                ],
            }
        ],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "brand_name": "PACT Authorization Gateway",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                }
            }
        },
    }
    response = await _authed(
        "POST", "/v2/checkout/orders", "order creation", request_id=f"order-{idempotency_key}",
        prefer=PREFER_FULL, json=payload,
    )
    if response.status_code not in (200, 201):
        raise _parse_error(response, "order creation")
    data = response.json()
    return {
        "order_id": data.get("id"),
        "status": data.get("status"),
        "approve_url": _approve_link(data),
        "raw": data,
    }


async def get_order_details(order_id: str) -> Dict[str, Any]:
    """Retrieve current details for a PayPal order (server-side source of truth)."""
    response = await _authed("GET", f"/v2/checkout/orders/{order_id}", "order lookup")
    if response.status_code != 200:
        raise _parse_error(response, "order lookup")
    return response.json()


async def capture_order(order_id: str, idempotency_key: str) -> Dict[str, Any]:
    """Capture an approved order. PayPal-Request-Id makes retries return the same capture."""
    response = await _authed(
        "POST", f"/v2/checkout/orders/{order_id}/capture", "payment capture", request_id=f"cap-{idempotency_key}",
        prefer=PREFER_FULL,
    )
    if response.status_code not in (200, 201):
        raise _parse_error(response, "payment capture")
    return response.json()


# ----------------------------------------------------------------------------
# Response interpretation helpers (pure, unit-tested)
# ----------------------------------------------------------------------------

def first_purchase_unit(order: Dict[str, Any]) -> Dict[str, Any]:
    units = order.get("purchase_units") or []
    return units[0] if units and isinstance(units[0], dict) else {}


def extract_captures(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    unit = first_purchase_unit(order)
    captures = ((unit.get("payments") or {}).get("captures")) or []
    return [c for c in captures if isinstance(c, dict)]


def verify_order_matches(
    order: Dict[str, Any],
    *,
    order_id: str,
    proposal_id: str,
    mandate_id: str,
    amount: Decimal,
    currency: str,
) -> List[str]:
    """Return a list of mismatches between a PayPal order and the approved proposal."""
    problems: List[str] = []
    if order.get("id") != order_id:
        problems.append(f"Order ID mismatch: expected {order_id}, PayPal returned {order.get('id')}.")
    unit = first_purchase_unit(order)
    if not unit:
        problems.append("PayPal order has no purchase unit.")
        return problems
    if unit.get("reference_id") != proposal_id:
        problems.append("Purchase unit reference does not match this proposal.")
    # custom_id is not always echoed by GET; only compare when present.
    if unit.get("custom_id") not in (None, mandate_id):
        problems.append("Purchase unit is bound to a different mandate.")
    amt = unit.get("amount") or {}
    if amt.get("currency_code") != currency:
        problems.append(f"Currency mismatch: expected {currency}, PayPal has {amt.get('currency_code')}.")
    if amt.get("value") != paypal_value(amount):
        problems.append(f"Amount mismatch: expected {paypal_value(amount)}, PayPal has {amt.get('value')}.")
    return problems


def describe_sandbox_status() -> Dict[str, Any]:
    s = _settings()
    return {
        "environment": "sandbox" if s.paypal_is_sandbox else "INVALID (non-sandbox URL rejected)",
        "api_host": s.paypal_api_host,
        "sandbox_enforced": True,
        "credentials_configured": s.paypal_credentials_configured,
        "currency": s.currency,
        "return_base_url": s.app_base_url,
    }
