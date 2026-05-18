#!/usr/bin/env python3
"""
Deduplicate properties across portals.

Usage:
    python3 dedupe.py <file1.json> <file2.json> ...

Output:
    Unique properties with merged data
"""

import json
import re
import sys
from difflib import SequenceMatcher
from typing import List, Dict, Any


def normalize_address(addr: str) -> str:
    """Normalize address for matching."""
    addr = addr.lower()
    addr = addr.replace(',', '').replace('.', '')
    addr = addr.replace(' street', ' st').replace(' road', ' rd')
    addr = addr.replace(' avenue', ' ave').replace(' drive', ' dr')
    addr = ' '.join(addr.split())  # Normalize whitespace
    return addr


STREET_SUFFIXES = {
    "st", "street", "rd", "road", "ave", "avenue", "dr", "drive", "crescent",
    "place", "terrace", "gardens", "garden", "lane", "court", "way", "close",
    "park", "view", "walk", "mews", "square", "loan", "riggs", "brae",
}

LOCATION_WORDS = {
    "edinburgh", "glasgow", "fife", "kirkcaldy", "dunfermline", "leven", "rosyth",
    "cowdenbeath", "falkland", "dalkeith", "bonnyrigg", "midlothian", "lothian",
    "east", "west", "north", "south", "scotland", "shire", "county",
}


def street_tokens(addr: str) -> set:
    """Extract street-specific words so similar towns/postcodes do not cause false matches."""
    first_part = (addr or "").split(",", 1)[0].lower()
    tokens = re.findall(r"[a-z]+", first_part)
    return {
        token for token in tokens
        if len(token) > 2
        and token not in STREET_SUFFIXES
        and token not in LOCATION_WORDS
        and not re.match(r"^[a-z]{1,2}\d*$", token)
    }


def addresses_match(addr1: str, addr2: str, threshold: float = 0.85) -> bool:
    """Check if two addresses match without merging nearby but distinct streets."""
    norm1 = normalize_address(addr1)
    norm2 = normalize_address(addr2)

    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    tokens1 = street_tokens(addr1)
    tokens2 = street_tokens(addr2)

    if similarity < threshold:
        # Cross-portal rows often differ by flat/unit number or postcode suffix.
        # Allow a small dip only when the street-specific tokens still agree.
        if similarity < 0.80 or not tokens1 or not tokens2 or tokens1.isdisjoint(tokens2):
            return False

    if tokens1 and tokens2 and tokens1.isdisjoint(tokens2):
        return False

    return True


def same_portal_identity(prop1: Dict[str, Any], prop2: Dict[str, Any]) -> bool:
    """Same-portal rows are duplicates only when the portal id or URL matches.

    Rightmove can list multiple flats on the same street, sometimes with identical
    display addresses. Address-only matching merges distinct flats and contaminates
    price/image data.
    """
    if prop1.get('portal') != prop2.get('portal'):
        return False

    id1, id2 = str(prop1.get('id') or ''), str(prop2.get('id') or '')
    if id1 and id2 and id1 == id2:
        return True

    url1, url2 = prop1.get('url') or '', prop2.get('url') or ''
    return bool(url1 and url2 and url1 == url2)


def properties_match(prop1: Dict[str, Any], prop2: Dict[str, Any], threshold: float = 0.85) -> bool:
    """Return true when two rows represent the same property."""
    if prop1.get('portal') == prop2.get('portal'):
        return same_portal_identity(prop1, prop2)

    return addresses_match(prop1.get('address', ''), prop2.get('address', ''), threshold)


def merge_property_data(duplicates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge data from duplicate properties across portals."""
    # Start with first property as base
    merged = duplicates[0].copy()

    # Collect all unique images, preserving source order.
    all_images = []
    seen_images = set()
    for prop in duplicates:
        for image in prop.get('images', []):
            if image and image not in seen_images:
                seen_images.add(image)
                all_images.append(image)
    merged['images'] = all_images

    # Take best price (lowest non-zero)
    prices = [p['price'] for p in duplicates if p.get('price', 0) > 0]
    if prices:
        merged['price'] = min(prices)

    # Take highest bed/bath counts
    merged['beds'] = max(p.get('beds', 0) for p in duplicates)
    merged['baths'] = max(p.get('baths', 0) for p in duplicates)

    # Track which portals have this property
    merged['portals'] = [p['portal'] for p in duplicates]

    # Keep all URLs
    merged['urls'] = {p['portal']: p['url'] for p in duplicates}

    # Use best image URL
    image_urls = [p.get('image_url', '') for p in duplicates if p.get('image_url')]
    if image_urls:
        merged['image_url'] = image_urls[0]

    # Combine features, including structured feature objects.
    all_features = []
    seen_features = set()
    for prop in duplicates:
        for feature in prop.get('features', []):
            key = json.dumps(feature, sort_keys=True) if isinstance(feature, dict) else str(feature)
            if key not in seen_features:
                seen_features.add(key)
                all_features.append(feature)
    merged['features'] = all_features

    # Use longest description
    descriptions = [p.get('description', '') for p in duplicates]
    merged['description'] = max(descriptions, key=len) if descriptions else ''

    return merged


def deduplicate(properties: List[Dict[str, Any]], threshold: float = 0.85) -> List[Dict[str, Any]]:
    """
    Deduplicate properties by address similarity.

    Args:
        properties: List of property dicts
        threshold: Similarity score 0-1 (default 0.85 = 85% match)

    Returns:
        List of unique properties with merged data
    """
    unique = []
    processed_indices = set()

    for i, prop in enumerate(properties):
        if i in processed_indices:
            continue

        # Find all duplicates of this property
        duplicates = [prop]
        processed_indices.add(i)

        for j, other in enumerate(properties[i+1:], start=i+1):
            if j in processed_indices:
                continue

            if properties_match(prop, other, threshold):
                duplicates.append(other)
                processed_indices.add(j)

        # Merge duplicate data
        if len(duplicates) > 1:
            merged = merge_property_data(duplicates)
            unique.append(merged)
        else:
            unique.append(prop)

    return unique


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dedupe.py <file1.json> <file2.json> ...")
        print("\nExample:")
        print("  python3 dedupe.py cache/espc.json cache/rightmove.json cache/zoopla.json")
        sys.exit(1)

    # Load all properties from input files
    all_properties = []
    for filename in sys.argv[1:]:
        try:
            with open(filename) as f:
                data = json.load(f)
                properties = data.get('properties', data) if isinstance(data, dict) else data
                all_properties.extend(properties)
        except Exception as e:
            print(f"Error loading {filename}: {e}", file=sys.stderr)
            continue

    # Deduplicate
    original_count = len(all_properties)
    unique = deduplicate(all_properties)
    duplicate_count = original_count - len(unique)

    # Output
    result = {
        'deduplication': {
            'original_count': original_count,
            'unique_count': len(unique),
            'duplicate_count': duplicate_count,
            'duplicate_percentage': round((duplicate_count / original_count) * 100, 1) if original_count > 0 else 0
        },
        'properties': unique
    }

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
