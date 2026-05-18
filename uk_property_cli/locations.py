"""Small location resolver for portal-specific identifiers.

This is intentionally explicit. Portal IDs are vendor magic; the CLI should hide
that from agents and humans where possible.
"""

from __future__ import annotations

from typing import Dict, List

RIGHTMOVE_LOCATIONS: Dict[str, str] = {
    "edinburgh": "REGION^475",
    "edinburgh-city": "REGION^475",
    "edinburgh-and-lothian": "REGION^95850",
    "fife": "REGION^61347",
    "falkirk": "REGION^501",
    "glasgow": "REGION^550",
    "manchester": "REGION^904",
    "london": "REGION^93917",
}

ESPC_LOCATIONS: Dict[str, str] = {
    "edinburgh": "edinburgh",
    "east-lothian": "east-lothian",
    "midlothian": "midlothian",
    "west-lothian": "west-lothian",
    "fife": "fife",
}

ZOOPLA_LOCATIONS: Dict[str, str] = {
    "edinburgh": "edinburgh",
    "glasgow": "glasgow",
    "manchester": "manchester",
    "london": "london",
}


def normalise_location(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "-").replace("_", "-")


def resolve(portal: str, location: str) -> str:
    portal = portal.lower()
    if not location:
        location = "edinburgh"

    # If a caller already supplied a Rightmove REGION^id, keep it.
    if portal == "rightmove" and location.upper().startswith("REGION^"):
        return location

    key = normalise_location(location)
    maps = {
        "rightmove": RIGHTMOVE_LOCATIONS,
        "espc": ESPC_LOCATIONS,
        "zoopla": ZOOPLA_LOCATIONS,
    }
    mapping = maps.get(portal, {})
    return mapping.get(key, location)


def find(query: str = "") -> List[Dict[str, str]]:
    q = normalise_location(query)
    rows = []
    for portal, mapping in [("rightmove", RIGHTMOVE_LOCATIONS), ("espc", ESPC_LOCATIONS), ("zoopla", ZOOPLA_LOCATIONS)]:
        for name, value in mapping.items():
            if not q or q in name or q in value.lower():
                rows.append({"portal": portal, "name": name, "value": value})
    return rows
