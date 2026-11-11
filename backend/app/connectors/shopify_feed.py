"""Reads a store's catalog in Shopify's `products.json` format (products with priced variants)."""

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List

from app.connectors.base import ConnectorError, MerchantConnector, Offer
from app.money import q

_TAG = re.compile(r"<[^>]+>")


class ShopifyFeedConnector(MerchantConnector):
    platform = "Shopify (products.json)"

    def __init__(self, id: str, store_name: str, feed: Path, currency: str = "USD", description: str = ""):
        self.id = id
        self.name = store_name
        self.feed = feed
        self.currency = currency
        self.description = description

    def fetch_offers(self) -> List[Offer]:
        try:
            data = json.loads(self.feed.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConnectorError(f"Could not read the {self.name} feed: {type(exc).__name__}") from exc
        products = data.get("products") if isinstance(data, dict) else None
        if not isinstance(products, list):
            raise ConnectorError(f"The {self.name} feed has no 'products' list.")

        offers: List[Offer] = []
        for p in products:
            title = str(p.get("title") or "").strip()
            if not title:
                continue
            body = " ".join(_TAG.sub(" ", str(p.get("body_html") or "")).split())
            images = p.get("images") or []
            image = images[0].get("src") if images and isinstance(images[0], dict) else None
            for v in p.get("variants") or []:
                try:
                    price = q(Decimal(str(v.get("price"))))
                except (InvalidOperation, TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                variant = str(v.get("title") or "").strip()
                offers.append(Offer(
                    external_id=f"{p.get('id')}:{v.get('id')}",
                    name=title if variant in ("", "Default Title") else f"{title} ({variant})",
                    description=body[:1000],
                    price=price,
                    currency=self.currency,
                    category=str(p.get("product_type") or "General").strip() or "General",
                    merchant=self.name,
                    in_stock=bool(v.get("available", True)),
                    image_url=image,
                ))
        return offers
