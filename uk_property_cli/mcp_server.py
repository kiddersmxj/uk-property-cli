"""Minimal MCP stdio server for uk-property-cli.

This intentionally avoids the MCP Python SDK so the package stays dependency-free.
It implements the JSON-RPC methods agents need: initialise, list tools and call
tools. Tool outputs are JSON text so clients can pass them straight to downstream
reasoning or storage steps.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .compare import compare_snapshots
from .config import load_profile
from .dedupe import deduplicate_with_report
from .filters import filter_properties_with_reasons
from .locations import find as find_locations
from .portals import ADAPTERS, SearchConfig
from .schema import utc_now_iso
from .scoring import rank_properties

JsonDict = Dict[str, Any]


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, "", "none", "null"):
        return None
    return int(value)


def _csv(value: Any) -> Optional[List[str]]:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    return [x.strip() for x in str(value).split(",") if x.strip()]


def search_properties(arguments: JsonDict) -> JsonDict:
    profile = load_profile(arguments.get("profile", "")) if arguments.get("profile") else load_profile("")
    search = profile.get("search", {})

    config = SearchConfig(
        min_beds=int(arguments.get("min_beds") or search.get("min_beds") or 1),
        max_price=str(arguments.get("max_price") if arguments.get("max_price") is not None else (search.get("max_price") or "")),
        property_types=arguments.get("property_types") or ",".join(search.get("property_types") or []),
        location=arguments.get("location") or search.get("location") or "edinburgh",
        location_id=arguments.get("location_id") or "",
        max_pages=int(arguments.get("max_pages") or search.get("max_pages") or 3),
    )

    portal_arg = arguments.get("portal", "all")
    portals = ["rightmove", "espc", "zoopla"] if portal_arg == "all" else [portal_arg]
    if any(portal not in ADAPTERS for portal in portals):
        raise ValueError(f"Unknown portal: {portal_arg}")

    all_properties: List[JsonDict] = []
    portal_results = []
    for portal in portals:
        result = ADAPTERS[portal]().search(config)
        portal_results.append({k: v for k, v in result.items() if k != "properties"})
        all_properties.extend(result.get("properties", []))

    result: JsonDict = {
        "tool": "uk-property-cli-mcp",
        "version": __version__,
        "fetched_at": utc_now_iso(),
        "query": arguments,
        "portal_results": portal_results,
        "count": len(all_properties),
        "properties": all_properties,
    }

    if arguments.get("dedupe") or profile.get("deduplication", {}).get("enabled"):
        dconf = profile.get("deduplication", {})
        deduped = deduplicate_with_report(
            result["properties"],
            threshold=float(arguments.get("dedupe_threshold") or dconf.get("threshold", 0.88)),
            candidate_threshold=float(arguments.get("candidate_threshold") or dconf.get("candidate_threshold", 0.72)),
        )
        result.update(deduped)
        result["count"] = len(result["properties"])

    if arguments.get("apply_filters"):
        areas = _csv(arguments.get("areas")) or profile.get("areas", {}).get("desired") or None
        exclude = _csv(arguments.get("exclude")) or profile.get("areas", {}).get("excluded") or None
        kept, removed = filter_properties_with_reasons(
            result["properties"],
            areas=areas,
            exclude=exclude,
            min_price=_int_or_none(arguments.get("min_price")),
            max_price=_int_or_none(arguments.get("max_price")),
            min_beds=_int_or_none(arguments.get("min_beds")),
            max_beds=_int_or_none(arguments.get("max_beds")),
            category=arguments.get("category"),
        )
        result["filtering"] = {"original_count": len(result["properties"]), "filtered_count": len(kept), "removed_count": len(removed)}
        if arguments.get("explain"):
            result["removed_properties"] = removed
        result["properties"] = kept
        result["count"] = len(kept)

    if arguments.get("rank"):
        result["properties"] = rank_properties(result["properties"], profile)

    return result


def list_locations(arguments: JsonDict) -> JsonDict:
    return {"locations": find_locations(arguments.get("query", ""))}


def dedupe_properties(arguments: JsonDict) -> JsonDict:
    properties = arguments.get("properties") or []
    if not isinstance(properties, list):
        raise ValueError("properties must be a list")
    return deduplicate_with_report(
        properties,
        threshold=float(arguments.get("threshold", 0.88)),
        candidate_threshold=float(arguments.get("candidate_threshold", 0.72)),
    )


def filter_properties(arguments: JsonDict) -> JsonDict:
    properties = arguments.get("properties") or []
    if not isinstance(properties, list):
        raise ValueError("properties must be a list")
    kept, removed = filter_properties_with_reasons(
        properties,
        areas=_csv(arguments.get("areas")),
        exclude=_csv(arguments.get("exclude")),
        min_price=_int_or_none(arguments.get("min_price")),
        max_price=_int_or_none(arguments.get("max_price")),
        min_beds=_int_or_none(arguments.get("min_beds")),
        max_beds=_int_or_none(arguments.get("max_beds")),
        category=arguments.get("category"),
    )
    result = {"filtering": {"original_count": len(properties), "filtered_count": len(kept), "removed_count": len(removed)}, "properties": kept}
    if arguments.get("explain"):
        result["removed_properties"] = removed
    return result


def compare_properties(arguments: JsonDict) -> JsonDict:
    old = arguments.get("old_properties") or []
    new = arguments.get("new_properties") or []
    if not isinstance(old, list) or not isinstance(new, list):
        raise ValueError("old_properties and new_properties must be lists")
    return compare_snapshots(old, new)


TOOLS: Dict[str, Dict[str, Any]] = {
    "uk_property_search": {
        "description": "Search Rightmove, ESPC, Zoopla or all portals and return normalised property-listing.v1 JSON.",
        "handler": search_properties,
        "inputSchema": {
            "type": "object",
            "properties": {
                "portal": {"type": "string", "enum": ["all", "rightmove", "espc", "zoopla"], "default": "all"},
                "location": {"type": "string", "default": "edinburgh"},
                "location_id": {"type": "string", "description": "Optional portal-specific location id, e.g. REGION^475"},
                "min_beds": {"type": "integer", "default": 1},
                "max_beds": {"type": "integer"},
                "min_price": {"type": "integer"},
                "max_price": {"type": "integer"},
                "property_types": {"type": "string", "description": "Portal-specific comma string such as flat"},
                "max_pages": {"type": "integer", "default": 3},
                "dedupe": {"type": "boolean", "default": False},
                "apply_filters": {"type": "boolean", "default": False},
                "areas": {"type": "string", "description": "Comma-separated desired postcodes/areas"},
                "exclude": {"type": "string", "description": "Comma-separated excluded postcodes/areas"},
                "category": {"type": "string", "enum": ["investment", "family", "other"]},
                "rank": {"type": "boolean", "default": False},
                "profile": {"type": "string", "description": "Optional local/private JSON profile path"},
            },
        },
    },
    "uk_property_locations": {
        "description": "Find known portal location identifiers for a city/area.",
        "handler": list_locations,
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    "uk_property_dedupe": {
        "description": "Deduplicate an array of property listings and report fuzzy candidates.",
        "handler": dedupe_properties,
        "inputSchema": {"type": "object", "properties": {"properties": {"type": "array"}, "threshold": {"type": "number"}, "candidate_threshold": {"type": "number"}}, "required": ["properties"]},
    },
    "uk_property_filter": {
        "description": "Filter an array of property listings with optional removal reasons.",
        "handler": filter_properties,
        "inputSchema": {"type": "object", "properties": {"properties": {"type": "array"}, "areas": {"type": "string"}, "exclude": {"type": "string"}, "min_price": {"type": "integer"}, "max_price": {"type": "integer"}, "min_beds": {"type": "integer"}, "max_beds": {"type": "integer"}, "category": {"type": "string"}, "explain": {"type": "boolean"}}, "required": ["properties"]},
    },
    "uk_property_compare": {
        "description": "Compare two property snapshots for new, removed and changed listings.",
        "handler": compare_properties,
        "inputSchema": {"type": "object", "properties": {"old_properties": {"type": "array"}, "new_properties": {"type": "array"}}, "required": ["old_properties", "new_properties"]},
    },
}


def tool_descriptions() -> List[JsonDict]:
    return [{"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]} for name, spec in TOOLS.items()]


def _success(request_id: Any, result: JsonDict) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(request: JsonDict) -> Optional[JsonDict]:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        return _success(request_id, {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "uk-property-cli", "version": __version__},
        })
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _success(request_id, {"tools": tool_descriptions()})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            result = TOOLS[name]["handler"](arguments)
            return _success(request_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "isError": False})
        except Exception as exc:  # noqa: BLE001 - MCP must return tool errors, not crash.
            return _success(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle_request(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            response = _error(None, -32700, f"Parse error: {exc}")
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
