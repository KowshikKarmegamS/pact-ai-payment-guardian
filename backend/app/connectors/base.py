"""The interface every merchant platform plugs into.

A connector only *supplies offers*. It never decides, approves or pays: offers are synced into
PACT's catalog, and from there the same policy engine, approval fingerprint and PayPal flow apply
to every source. Adding a platform means writing one `fetch_offers()`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urlsplit, urlunsplit


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
    brand: Optional[str] = None
    purchase_url: Optional[str] = None


class ConnectorError(Exception):
    """The source could not be read or returned malformed data."""


class MerchantConnector(ABC):
    id: str
    name: str
    platform: str
    description: str
    # A full feed lists every offer, so offers missing from a sync are delisted. A search API does not.
    full_feed: bool = True

    @property
    def configured(self) -> bool:
        return True

    @abstractmethod
    def fetch_offers(self) -> List[Offer]:
        """Return the source's current offers. Raise ConnectorError if the source cannot be read."""


def stable_buy_link(url: Optional[str]) -> Optional[str]:
    """The link's identity: scheme, host and path. Channel3 links identify the listing in the path
    (product, retailer, account) and add per-request tracking ids in the query, which differ on every read."""
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
