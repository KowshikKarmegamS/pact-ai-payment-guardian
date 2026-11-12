"""Merchant connector registry."""

from pathlib import Path
from typing import Dict, List, Optional

from app.connectors.base import ConnectorError, MerchantConnector, Offer
from app.connectors.channel3 import Channel3Connector, Channel3Error
from app.connectors.shopify_feed import ShopifyFeedConnector

BUILTIN_SOURCE = "pact-catalog"

_FEEDS = Path(__file__).resolve().parent / "feeds"

CONNECTORS: Dict[str, MerchantConnector] = {
    c.id: c
    for c in (
        Channel3Connector(),
        ShopifyFeedConnector(
            id="northwind-supply",
            store_name="Northwind Supply",
            feed=_FEEDS / "northwind-supply.products.json",
            description="Demo office-gear store exported in Shopify's products.json format.",
        ),
    )
}


def get_connector(connector_id: str) -> Optional[MerchantConnector]:
    return CONNECTORS.get(connector_id)


def all_connectors() -> List[MerchantConnector]:
    return list(CONNECTORS.values())


__all__ = ["BUILTIN_SOURCE", "CONNECTORS", "Channel3Connector", "Channel3Error", "ConnectorError", "MerchantConnector", "Offer", "all_connectors", "get_connector"]
