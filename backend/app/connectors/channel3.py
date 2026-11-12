"""Live retailer offers from Channel3 (https://docs.trychannel3.com): 100M+ products across 25k+ retailers.

Channel3 returns products with one offer per retailer. Each offer becomes one PACT catalog item:
merchant = the retailer's domain, price and availability from the offer, and the offer's buy link.
The connector only reads offers. Deciding, approving and paying stay with PACT and the human.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.connectors.base import ConnectorError, MerchantConnector, Offer
from app.money import q


class Channel3Error(ConnectorError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _https(url: Any) -> Optional[str]:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url.strip())
    return url.strip() if parsed.scheme == "https" and parsed.netloc else None


def normalize_product(p: Dict[str, Any], currency: str) -> List[Offer]:
    """One Offer per retailer offer that is priced in PACT's currency and has a valid buy link."""
    pid = str(p.get("id") or "").strip()
    title = str(p.get("title") or "").strip()
    if not pid or not title:
        return []
    cat = p.get("category") or {}
    path = cat.get("path") or []
    top = (path[0].get("title") if path and isinstance(path[0], dict) else None) or cat.get("title") or "General"
    brands = p.get("brands") or []
    brand = brands[0].get("name") if brands and isinstance(brands[0], dict) else None
    images = p.get("images") or []
    main = next((i for i in images if isinstance(i, dict) and i.get("is_main_image")), images[0] if images else None)
    image = _https(main.get("url")) if isinstance(main, dict) else None
    desc = " ".join(str(p.get("description") or "").split())[:1000]

    offers: List[Offer] = []
    seen = set()
    for o in p.get("offers") or []:
        if not isinstance(o, dict):
            continue
        domain = str(o.get("domain") or "").strip().lower()
        price = o.get("price") or {}
        url = _https(o.get("url"))
        if not domain or not url or domain in seen:
            continue
        if str(price.get("currency") or "").upper() != currency.upper():
            continue
        try:
            amount = q(Decimal(str(price.get("price"))))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        seen.add(domain)
        offers.append(Offer(
            external_id=f"{pid}:{domain}"[:120],
            name=title[:255],
            description=desc,
            price=amount,
            currency=currency.upper(),
            category=str(top)[:100],
            merchant=domain[:100],
            in_stock=o.get("availability") == "InStock",
            image_url=image,
            brand=(brand or None) and str(brand)[:120],
            purchase_url=url[:1000],
        ))
    return offers


class Channel3Connector(MerchantConnector):
    id = "channel3"
    name = "Channel3"
    platform = "Channel3 API"
    description = "Live product search across 100M+ products from 25,000+ retailers."
    full_feed = False

    def __init__(self, transport: Optional[httpx.BaseTransport] = None):
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(get_settings().CHANNEL3_API_KEY.strip())

    def _client(self) -> httpx.Client:
        s = get_settings()
        if not self.configured:
            raise Channel3Error("Channel3 is not configured: set CHANNEL3_API_KEY on the server.", 503)
        return httpx.Client(
            base_url=s.CHANNEL3_BASE_URL.rstrip("/"),
            headers={"x-api-key": s.CHANNEL3_API_KEY.strip(), "Accept": "application/json"},
            timeout=s.CHANNEL3_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    def _call(self, method: str, path: str, **kw) -> Dict[str, Any]:
        try:
            with self._client() as c:
                r = c.request(method, path, **kw)
        except httpx.TimeoutException as exc:
            raise Channel3Error("Channel3 did not answer in time.", 504) from exc
        except httpx.HTTPError as exc:
            raise Channel3Error(f"Could not reach Channel3 ({type(exc).__name__}).", 502) from exc
        if r.status_code == 404:
            raise Channel3Error("Channel3 no longer lists this product.", 404)
        if r.status_code in (401, 403):
            raise Channel3Error("Channel3 rejected the API key.", 502)
        if r.status_code == 402:
            raise Channel3Error("The Channel3 account is out of credits.", 502)
        if r.status_code == 429:
            raise Channel3Error("Channel3 rate limit reached; try again in a few seconds.", 503)
        if r.status_code >= 400:
            raise Channel3Error(f"Channel3 returned HTTP {r.status_code}.", 502)
        try:
            data = r.json()
        except ValueError as exc:
            raise Channel3Error("Channel3 returned a response that is not JSON.", 502) from exc
        if not isinstance(data, dict):
            raise Channel3Error("Channel3 returned an unexpected response.", 502)
        return data

    def search(self, query: str, limit: int = 10, max_price: Optional[Decimal] = None) -> List[Offer]:
        cur = get_settings().currency
        body: Dict[str, Any] = {"query": query.strip()[:300], "limit": max(1, min(int(limit), 30)),
                                "config": {"currency": cur, "country": "US"}}
        if max_price is not None:
            body["filters"] = {"price": {"max_price": float(max_price)}}
        data = self._call("POST", "/v1/search", json=body)
        products = data.get("products")
        if not isinstance(products, list):
            raise Channel3Error("Channel3 search response has no 'products' list.", 502)
        offers: List[Offer] = []
        for p in products:
            if isinstance(p, dict):
                offers.extend(normalize_product(p, cur))
        return offers

    def product_offers(self, product_id: str) -> List[Offer]:
        cur = get_settings().currency
        data = self._call("GET", f"/v1/products/{product_id}", params={"currency": cur, "country": "US"})
        return normalize_product(data, cur)

    def fetch_offers(self) -> List[Offer]:
        queries = [x.strip() for x in get_settings().CHANNEL3_SYNC_QUERIES.split(",") if x.strip()]
        offers: List[Offer] = []
        for query in queries[:10]:
            offers.extend(self.search(query, limit=6))
        return offers
