#!/usr/bin/env python3
"""Backward-compatible wrapper for uk-property filter."""

from uk_property_cli.cli import main

if __name__ == "__main__":
    import sys
    main(["filter", *sys.argv[1:]])
