#!/usr/bin/env python3
"""Backward-compatible wrapper for uk-property compare."""

from uk_property_cli.compare import compare_snapshots  # noqa: F401
from uk_property_cli.cli import main

if __name__ == "__main__":
    import sys
    main(["compare", *sys.argv[1:]])
