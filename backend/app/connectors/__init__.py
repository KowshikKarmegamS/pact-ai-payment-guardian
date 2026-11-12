"""Merchant connector registry."""

from typing import Dict, List, Optional

from app.connectors.base import ConnectorError, MerchantConnector, Offer
from app.connectors.channel3 import Channel3Connector, Channel3Error
from app.connectors.demo_store import DemoStoreConnector

DEMO_STORE = "demo-store"

CONNECTORS: Dict[str, MerchantConnector] = {c.id: c for c in (Channel3Connector(), DemoStoreConnector())}


def get_connector(connector_id: str) -> Optional[MerchantConnector]:
    return CONNECTORS.get(connector_id)


def all_connectors() -> List[MerchantConnector]:
    return list(CONNECTORS.values())


__all__ = ["DEMO_STORE", "CONNECTORS", "Channel3Connector", "Channel3Error", "DemoStoreConnector", "ConnectorError", "MerchantConnector", "Offer", "all_connectors", "get_connector"]
