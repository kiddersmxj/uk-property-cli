"""Command-line interface for uk-property."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .compare import compare_snapshots
from .config import load_profile
from .dedupe import deduplicate_with_report
from .filters import filter_properties_with_reasons
from .io import dump_result, load_properties, write_json
from .locations import find as find_locations, resolve
from .portals import ADAPTERS, SearchConfig
from .schema import utc_now_iso
from .scoring import rank_properties


def _int_or_none(value: Optional[str]) -> Optional[int]:
    if value in (None, "", "none", "null"):
        return None
    return int(value)


def build_search_config(args: argparse.Namespace, profile: Dict[str, Any]) -> SearchConfig:
    search = profile.get("search", {})
    return SearchConfig(
        min_beds=int(args.min_beds or search.get("min_beds") or 1),
        max_price=str(args.max_price if args.max_price is not None else (search.get("max_price") or "")),
        property_types=args.property_types or ",".join(search.get("property_types") or []),
        location=args.location or search.get("location") or "edinburgh",
        location_id=args.location_id or "",
        max_pages=int(args.max_pages or search.get("max_pages") or 3),
    )


def command_search(args: argparse.Namespace) -> None:
    profile = load_profile(args.profile) if args.profile else load_profile("")
    config = build_search_config(args, profile)
    portals = ["rightmove", "espc", "zoopla"] if args.portal == "all" else [args.portal]

    all_properties: List[Dict[str, Any]] = []
    portal_results = []
    for portal in portals:
        adapter = ADAPTERS[portal]()
        result = adapter.search(config)
        portal_results.append({k: v for k, v in result.items() if k != "properties"})
        all_properties.extend(result.get("properties", []))

    query = {k: v for k, v in vars(args).items() if k != "func"}
    result: Dict[str, Any] = {
        "tool": "uk-property-cli",
        "version": __version__,
        "fetched_at": utc_now_iso(),
        "query": query,
        "portal_results": portal_results,
        "count": len(all_properties),
        "properties": all_properties,
    }

    if args.dedupe or profile.get("deduplication", {}).get("enabled"):
        dconf = profile.get("deduplication", {})
        deduped = deduplicate_with_report(
            result["properties"],
            threshold=float(args.dedupe_threshold or dconf.get("threshold", 0.88)),
            candidate_threshold=float(dconf.get("candidate_threshold", 0.72)),
        )
        result.update(deduped)
        result["count"] = len(result["properties"])

    criteria = {
        "areas": args.areas.split(",") if args.areas else profile.get("areas", {}).get("desired") or None,
        "exclude": args.exclude.split(",") if args.exclude else profile.get("areas", {}).get("excluded") or None,
        "min_price": _int_or_none(args.min_price),
        "max_price": _int_or_none(args.max_price),
        "min_beds": _int_or_none(args.min_beds),
        "max_beds": _int_or_none(args.max_beds),
        "category": args.category,
    }
    if args.apply_filters:
        kept, removed = filter_properties_with_reasons(result["properties"], **criteria)
        result["filtering"] = {"original_count": len(result["properties"]), "filtered_count": len(kept), "removed_count": len(removed), "criteria": criteria}
        if args.explain:
            result["removed_properties"] = removed
        result["properties"] = kept
        result["count"] = len(kept)

    if args.rank:
        result["properties"] = rank_properties(result["properties"], profile)

    if args.output:
        write_json(args.output, result)
    dump_result(result, jsonl=args.jsonl)


def command_dedupe(args: argparse.Namespace) -> None:
    props = []
    for path in args.files:
        props.extend(load_properties(path))
    result = deduplicate_with_report(props, threshold=args.threshold, candidate_threshold=args.candidate_threshold)
    dump_result(result, jsonl=args.jsonl)


def command_filter(args: argparse.Namespace) -> None:
    props = load_properties(args.input_file)
    kept, removed = filter_properties_with_reasons(
        props,
        areas=args.areas.split(",") if args.areas else None,
        exclude=args.exclude.split(",") if args.exclude else None,
        min_price=args.min_price,
        max_price=args.max_price,
        min_beds=args.min_beds,
        max_beds=args.max_beds,
        category=args.category,
    )
    result = {"filtering": {"original_count": len(props), "filtered_count": len(kept), "removed_count": len(removed)}, "properties": kept}
    if args.explain:
        result["removed_properties"] = removed
    dump_result(result, jsonl=args.jsonl)


def command_compare(args: argparse.Namespace) -> None:
    result = compare_snapshots(load_properties(args.old), load_properties(args.new))
    dump_result(result)


def command_locations(args: argparse.Namespace) -> None:
    rows = find_locations(args.query or "")
    print(json.dumps({"locations": rows}, indent=2))


def command_health(args: argparse.Namespace) -> None:
    statuses = []
    for name, klass in ADAPTERS.items():
        try:
            adapter = klass()
            config = SearchConfig(min_beds=1, max_pages=1, location=args.location or "edinburgh")
            result = adapter.search(config)
            statuses.append({"portal": name, "ok": "error" not in result, "count": result.get("count", 0), "error": result.get("error", "")})
        except Exception as exc:
            statuses.append({"portal": name, "ok": False, "error": str(exc)})
    print(json.dumps({"health": statuses}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uk-property", description="Search UK property portals with normalised JSON output")
    parser.add_argument("--version", action="version", version=f"uk-property {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search one or all portals")
    search.add_argument("--portal", choices=["all", "rightmove", "espc", "zoopla"], default="all")
    search.add_argument("--profile", help="Profile name/path from profiles/*.json")
    search.add_argument("--location", default="edinburgh")
    search.add_argument("--location-id", help="Portal-specific location id, e.g. REGION^475")
    search.add_argument("--min-beds")
    search.add_argument("--max-beds")
    search.add_argument("--min-price")
    search.add_argument("--max-price")
    search.add_argument("--property-types", default="")
    search.add_argument("--max-pages", type=int, default=3)
    search.add_argument("--category", choices=["investment", "family", "other"])
    search.add_argument("--areas", help="Comma-separated desired areas/postcodes")
    search.add_argument("--exclude", help="Comma-separated excluded areas/postcodes")
    search.add_argument("--apply-filters", action="store_true")
    search.add_argument("--explain", action="store_true")
    search.add_argument("--dedupe", action="store_true")
    search.add_argument("--dedupe-threshold", type=float)
    search.add_argument("--rank", action="store_true")
    search.add_argument("--jsonl", action="store_true")
    search.add_argument("--output")
    search.set_defaults(func=command_search)

    dedupe = sub.add_parser("dedupe", help="Deduplicate one or more JSON files")
    dedupe.add_argument("files", nargs="+")
    dedupe.add_argument("--threshold", type=float, default=0.88)
    dedupe.add_argument("--candidate-threshold", type=float, default=0.72)
    dedupe.add_argument("--jsonl", action="store_true")
    dedupe.set_defaults(func=command_dedupe)

    filt = sub.add_parser("filter", help="Filter a JSON property file")
    filt.add_argument("input_file")
    filt.add_argument("--areas")
    filt.add_argument("--exclude")
    filt.add_argument("--min-price", type=int)
    filt.add_argument("--max-price", type=int)
    filt.add_argument("--min-beds", type=int)
    filt.add_argument("--max-beds", type=int)
    filt.add_argument("--category", choices=["investment", "family", "other"])
    filt.add_argument("--explain", action="store_true")
    filt.add_argument("--jsonl", action="store_true")
    filt.set_defaults(func=command_filter)

    comp = sub.add_parser("compare", help="Compare two snapshots")
    comp.add_argument("old")
    comp.add_argument("new")
    comp.set_defaults(func=command_compare)

    loc = sub.add_parser("locations", help="Find known portal location identifiers")
    loc.add_argument("query", nargs="?", default="")
    loc.set_defaults(func=command_locations)

    health = sub.add_parser("health", help="Smoke-test portal adapters")
    health.add_argument("--location", default="edinburgh")
    health.set_defaults(func=command_health)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
