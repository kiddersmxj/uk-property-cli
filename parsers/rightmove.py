#!/usr/bin/env python3
"""Backward-compatible Rightmove parser wrapper."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uk_property_cli.portals.rightmove import legacy_main

if __name__ == "__main__":
    legacy_main()
