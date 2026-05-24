"""Normalised property listing schema.

The schema deliberately stays JSON-serialisable and dependency-free so agents can
consume it directly from stdout.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

SCHEMA_VERSION = "property-listing.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_price(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else 0


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


@dataclass
class PropertyListing:
    id: str
    portal: str
    url: str
    address: str
    price: int = 0
    price_text: str = "Price on application"
    beds: int = 0
    baths: int = 0
    title: str = "Property"
    property_type: str = "property"
    area: str = ""
    postcode: str = ""
    description: str = ""
    image_url: str = ""
    images: List[str] = field(default_factory=list)
    features: List[Any] = field(default_factory=list)
    category: str = "other"
    fetched_at: str = ""
    parser_version: str = ""
    fetch_url: str = ""
    source: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None

    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v not in (None, "", [], {}) or k in {"id", "portal", "url", "address", "price", "beds", "baths", "schema_version"}}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PropertyListing":
        images = data.get("images") or []
        if isinstance(images, str):
            images = [images]
        image_url = data.get("image_url") or (images[0] if images else "")
        price = parse_price(data.get("price", 0))
        beds = int(data.get("beds") or 0)
        baths = int(data.get("baths") or 0)
        address = clean_text(data.get("address", ""))
        portal = clean_text(data.get("portal", "unknown")).lower()
        listing_id = clean_text(data.get("id") or data.get("listing_id") or data.get("url") or address)

        return cls(
            id=listing_id,
            portal=portal,
            url=clean_text(data.get("url", "")),
            address=address,
            price=price,
            price_text=clean_text(data.get("price_text") or (f"£{price:,}" if price else "Price on application")),
            beds=beds,
            baths=baths,
            title=clean_text(data.get("title") or f"{beds}-bed property" if beds else "Property"),
            property_type=clean_text(data.get("property_type") or "property").lower(),
            area=clean_text(data.get("area", "")),
            postcode=clean_text(data.get("postcode", "")).upper(),
            description=clean_text(data.get("description", "")),
            image_url=image_url,
            images=[str(i) for i in images if i],
            features=data.get("features") or [],
            category=clean_text(data.get("category", "other")) or "other",
            fetched_at=clean_text(data.get("fetched_at", "")),
            parser_version=clean_text(data.get("parser_version", "")),
            fetch_url=clean_text(data.get("fetch_url", "")),
            source=data.get("source") or {},
            confidence=data.get("confidence"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


def normalise_listing(data: Dict[str, Any]) -> Dict[str, Any]:
    return PropertyListing.from_dict(data).to_dict()


def normalise_listings(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalise_listing(item) for item in items]
