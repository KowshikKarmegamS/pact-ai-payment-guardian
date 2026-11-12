"""PayPal Orders v2 request contract, checked against the PayPal Server SDK 2.4.0 reference (APIMatic Context Plugin).

No network: the module's single HTTP seam (`_request`) is replaced by a recorder.
"""

from decimal import Decimal

import httpx
import pytest

from app import paypal


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    async def fake_token(force_refresh=False):
        return "test-token"

    async def fake_request(method, path, *, context, headers, **kwargs):
        calls.append({"method": method, "path": path, "headers": dict(headers), "json": kwargs.get("json")})
        body = {"id": "ORDER1", "status": "PAYER_ACTION_REQUIRED",
                "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER1"}]}
        if path.endswith("/capture"):
            body = {"id": "ORDER1", "status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
                {"id": "CAP1", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "89.00"}}]}}]}
        return httpx.Response(201, json=body)

    monkeypatch.setattr(paypal, "get_access_token", fake_token)
    monkeypatch.setattr(paypal, "_request", fake_request)
    return calls


async def _create(name="Keychron K8 Pro Wireless Mechanical Keyboard", merchant="TechHub"):
    return await paypal.create_order(
        proposal_id="p-1", product_name=name, merchant=merchant, total_amount=Decimal("89.00"),
        price=Decimal("89.00"), quantity=1, mandate_id="m-1", idempotency_key="k" * 36, currency="USD",
        return_url="https://pact.test/return", cancel_url="https://pact.test/cancel",
    )


@pytest.mark.asyncio
async def test_create_and_capture_ask_for_the_full_representation(recorder):
    order = await _create()
    assert order["approve_url"].endswith("token=ORDER1")  # payer-action link (payment_source flow)
    cap = await paypal.capture_order("ORDER1", "k" * 36)
    create_call, capture_call = recorder
    for call in (create_call, capture_call):
        # Orders v2 defaults to return=minimal (id/status/links only); PACT needs payments.captures.
        assert call["headers"]["Prefer"] == "return=representation"
        assert call["headers"]["Authorization"] == "Bearer test-token"
        assert 1 <= len(call["headers"]["PayPal-Request-Id"]) <= 108  # SDK constraint
    assert create_call["headers"]["PayPal-Request-Id"] != capture_call["headers"]["PayPal-Request-Id"]
    assert paypal.extract_captures(cap)[0]["id"] == "CAP1"


@pytest.mark.asyncio
async def test_order_body_matches_sdk_constraints(recorder):
    await _create(name="Z" * 300, merchant="a-very-long-retailer-domain-name-example.com")
    body = recorder[0]["json"]
    unit = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE"
    assert len(unit["description"]) <= paypal.DESCRIPTION_MAX == 127
    item = unit["items"][0]
    assert 1 <= len(item["name"]) <= 127 and item["quantity"] == "1" and item["category"] == "PHYSICAL_GOODS"
    assert unit["amount"]["value"] == unit["amount"]["breakdown"]["item_total"]["value"] == "89.00"
    ctx = body["payment_source"]["paypal"]["experience_context"]
    assert ctx["user_action"] == "PAY_NOW" and ctx["shipping_preference"] == "NO_SHIPPING"
    assert len(ctx["brand_name"]) <= 127
    assert "application_context" not in body  # deprecated in favour of payment_source.experience_context


def test_short_descriptions_are_unchanged():
    assert paypal.order_description("Keychron K8 Pro", "TechHub") == "PACT authorized purchase: Keychron K8 Pro from TechHub"
