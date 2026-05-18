#!/usr/bin/env python3
"""Backward-compatible wrapper for uk_property_cli.dedupe."""

import json
import sys

from uk_property_cli.dedupe import *  # noqa: F401,F403
from uk_property_cli.dedupe import deduplicate_with_report
from uk_property_cli.io import load_properties


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dedupe.py <file1.json> <file2.json> ...")
        sys.exit(1)
    props = []
    for filename in sys.argv[1:]:
        try:
            props.extend(load_properties(filename))
        except Exception as exc:
            print(f"Error loading {filename}: {exc}", file=sys.stderr)
    print(json.dumps(deduplicate_with_report(props), indent=2))


if __name__ == "__main__":
    main()
