"""PayPal REST API v2 Integration (Sandbox).

Implements:
1. OAuth 2.0 client credentials token management
2. Orders API v2 order creation with exact proposal details
3. Orders API v2 payment capture with idempotency guarantees
4. Order retrieval and verification
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
import httpx
from app.config import get_settings

logger = logging.getLogger("pact.paypal")
settings = get_settings()

# In-memory token cache (access_token, expiration_epoch_seconds)
_token_cache: Tuple[Optional[str], float] = (None, 0.0)


class PayPalError(Exception):
    """Custom exception for PayPal integration errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


async def get_access_token() -> str:
    """Retrieve or refresh PayPal OAuth2 access token using client credentials."""
    global _token_cache
    current_time = time.time()
    cached_token, expiry = _token_cache

    # Reuse cached token if valid for at least another 60 seconds
    if cached_token and current_time < (expiry - 60):
        return cached_token

    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    base_url = settings.PAYPAL_BASE_URL.rstrip("/")

    if not client_id or not client_secret:
        raise PayPalError("PayPal Client ID or Secret is missing in configuration.")

    token_url = f"{base_url}/v1/oauth2/token"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
        except Exception as exc:
            logger.error(f"Failed to connect to PayPal token endpoint: {str(exc)}")
            raise PayPalError(f"PayPal connection error: {str(exc)}")

        if response.status_code != 200:
            logger.error(f"PayPal token acquisition failed: HTTP {response.status_code} - {response.text}")
            raise PayPalError(
                f"Failed to obtain PayPal access token: HTTP {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )

        data = response.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        if not token:
            raise PayPalError("PayPal token response did not contain access_token.")

        _token_cache = (token, current_time + float(expires_in))
        logger.info("Successfully acquired PayPal OAuth2 access token")
        return token


async def create_order(
    proposal_id: str,
    product_name: str,
    merchant: str,
    total_amount: Decimal,
    price: Decimal,
    quantity: int,
    mandate_id: str,
    idempotency_key: str,
    return_url: str = "http://localhost:5173/transactions?paypal=success",
    cancel_url: str = "http://localhost:5173/assistant?paypal=cancel",
) -> Dict[str, Any]:
    """Create a PayPal v2 checkout order tied to the exact proposal.

    The order strictly includes the approved merchant, price, and item details.
    """
    token = await get_access_token()
    base_url = settings.PAYPAL_BASE_URL.rstrip("/")
    order_url = f"{base_url}/v2/checkout/orders"

    formatted_total = f"{Decimal(str(total_amount)):.2f}"
    formatted_unit_price = f"{Decimal(str(price)):.2f}"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(proposal_id),
                "description": f"PACT Authorized Purchase: {product_name[:80]} from {merchant[:40]}",
                "custom_id": str(mandate_id),
                "amount": {
                    "currency_code": "USD",
                    "value": formatted_total,
                    "breakdown": {
                        "item_total": {
                            "currency_code": "USD",
                            "value": formatted_total,
                        }
                    },
                },
                "items": [
                    {
                        "name": product_name[:127],
                        "unit_amount": {
                            "currency_code": "USD",
                            "value": formatted_unit_price,
                        },
                        "quantity": str(quantity),
                        "category": "PHYSICAL_GOODS",
                    }
                ],
            }
        ],
        "application_context": {
            "brand_name": "PACT - AI Payment Guardian",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": str(idempotency_key),
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(order_url, json=payload, headers=headers)

        if response.status_code not in (200, 201):
            logger.error(f"PayPal order creation failed: {response.status_code} - {response.text}")
            raise PayPalError(
                f"PayPal order creation failed with status {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )

        data = response.json()
        order_id = data.get("id")
        links = data.get("links", [])
        approve_url = None

        for link in links:
            if link.get("rel") == "approve":
                approve_url = link.get("href")
                break

        return {
            "order_id": order_id,
            "status": data.get("status"),
            "approve_url": approve_url,
            "raw": data,
        }


async def capture_order(order_id: str, idempotency_key: str) -> Dict[str, Any]:
    """Capture payment for an approved PayPal order.

    Ensures idempotency via PayPal-Request-Id header.
    """
    token = await get_access_token()
    base_url = settings.PAYPAL_BASE_URL.rstrip("/")
    capture_url = f"{base_url}/v2/checkout/orders/{order_id}/capture"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": f"cap-{idempotency_key}",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(capture_url, headers=headers)

        if response.status_code not in (200, 201):
            logger.error(f"PayPal capture failed: {response.status_code} - {response.text}")
            raise PayPalError(
                f"PayPal payment capture failed with status {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )

        data = response.json()
        capture_id = None
        status = data.get("status")

        # Extract capture id from purchase units
        purchase_units = data.get("purchase_units", [])
        if purchase_units:
            payments = purchase_units[0].get("payments", {})
            captures = payments.get("captures", [])
            if captures:
                capture_id = captures[0].get("id")

        return {
            "order_id": order_id,
            "capture_id": capture_id,
            "status": status,
            "raw": data,
        }


async def get_order_details(order_id: str) -> Dict[str, Any]:
    """Retrieve current details for a PayPal order."""
    token = await get_access_token()
    base_url = settings.PAYPAL_BASE_URL.rstrip("/")
    url = f"{base_url}/v2/checkout/orders/{order_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise PayPalError(
                f"Failed to fetch order: {response.status_code}",
                status_code=response.status_code,
                details=response.text,
            )
        return response.json()
