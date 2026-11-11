"""The interface every merchant platform plugs into.

A connector only *supplies offers*. It never decides, approves or pays: offers are synced into
PACT's catalog, and from there the same policy engine, approval fingerprint and PayPal flow apply
to every source. Adding a platform means writing one `fetch_offers()`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class Offer:
    external_id: str
    name: str
    description: str
    price: Decimal
    currency: str
    category: str
    merchant: str
    in_stock: bool
    image_url: Optional[str] = None


class ConnectorError(Exception):
    """The source could not be read or returned malformed data."""


class MerchantConnector(ABC):
    id: str
    name: str
    platform: str
    description: str

    @abstractmethod
    def fetch_offers(self) -> List[Offer]:
        """Return the source's current offers. Raise ConnectorError if the source cannot be read."""
