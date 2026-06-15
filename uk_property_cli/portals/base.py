"""Portal adapter interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SearchConfig:
    min_beds: int = 1
    max_price: str = ""
    property_types: str = ""
    location: str = "edinburgh"
    location_id: str = ""
    max_pages: int = 3
    channel: str = "buy"
    extra: Dict[str, Any] = field(default_factory=dict)


class PortalAdapter:
    name = "base"
    parser_version = "0"

    def search(self, config: SearchConfig) -> Dict[str, Any]:
        raise NotImplementedError
