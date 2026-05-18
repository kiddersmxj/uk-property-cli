#!/usr/bin/env python3
"""
Rightmove Property Parser
Zero-dependency: curl + Python stdlib.

Default Edinburgh region: REGION^475, sortType=6 = newest first.
Optional regions/property types let agents run broader searches without creating
new scrapers. Paginates until results stop or MAX_PAGES is reached.
"""

import sys, json, subprocess, re
from datetime import datetime, timezone

BEDS = sys.argv[1] if len(sys.argv) > 1 else "4"
MAX_PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 3  # 24 per page → up to 72 results/location
# Optional comma-separated Rightmove location identifiers. Default remains Edinburgh.
# Examples: REGION^475 (Edinburgh), REGION^95850 (Edinburgh and Lothian), REGION^61347 (Fife), REGION^501 (Falkirk).
LOCATION_IDENTIFIERS = (sys.argv[3] if len(sys.argv) > 3 else "REGION^475").split(',')
MAX_PRICE = sys.argv[4] if len(sys.argv) > 4 else ""
PROPERTY_TYPES = sys.argv[5] if len(sys.argv) > 5 else ""

# Keep parser-level exclusions tiny. Downstream filters decide preferences;
# parser bans should only remove repeatedly unwanted local noise in the default setup.
BAD_AREAS = [
    "Moredun", "Niddrie", "Wester Hailes", "Sighthill",
    "Muirhouse", "Pilton", "Granton"
]


def fetch_page(beds, index=0, location_identifier="REGION^475"):
    """Fetch one Rightmove search-results page using curl."""
    loc = location_identifier.replace('^', '%5E')
    max_price = f"&maxPrice={MAX_PRICE}" if MAX_PRICE else ""
    property_types = f"&propertyTypes={PROPERTY_TYPES}" if PROPERTY_TYPES else ""
    url = (
        "https://www.rightmove.co.uk/property-for-sale/find.html"
        f"?locationIdentifier={loc}&minBedrooms={beds}{max_price}{property_types}&sortType=6&index={index}"
    )
    result = subprocess.run(
        [
            "curl", "-s", "--max-time", "15",
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "-H", "Accept-Language: en-GB,en;q=0.9",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.stdout


def extract_props_from_html(html):
    """Extract Rightmove's embedded Next.js searchResults JSON."""
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for script in scripts:
        if len(script) > 100000 and 'searchResults' in script:
            try:
                data = json.loads(script)
                search_results = data['props']['pageProps']['searchResults']
                return search_results.get('properties', []), search_results.get('resultCount', 0)
            except Exception:
                continue
    return [], 0


def is_bad_area(address):
    return any(bad.lower() in address.lower() for bad in BAD_AREAS)


def categorize(price, beds):
    if price < 250000:
        return "investment"
    if beds >= 4:
        return "family"
    return "other"


def parse_property(prop):
    address = prop.get('displayAddress', '')
    if is_bad_area(address):
        return None

    price = 0
    price_text = "Price on application"
    price_data = prop.get('price') or {}
    price = price_data.get('amount', 0) or 0
    display_price = (price_data.get('displayPrices') or [{}])[0]
    qualifier = (display_price.get('displayPriceQualifier') or '').strip()
    raw_price = (display_price.get('displayPrice') or '').strip()
    if qualifier and raw_price:
        price_text = f"{qualifier} {raw_price}"
    elif raw_price:
        price_text = raw_price
    elif price:
        price_text = f"£{price:,}"

    images = []
    property_images = prop.get('propertyImages') or {}
    for image in (property_images.get('images') or [])[:5]:
        src = image.get('srcUrl', '')
        if src:
            images.append(src)

    beds = prop.get('bedrooms', 0) or 0
    baths = prop.get('bathrooms', 0) or 0

    pc_match = re.search(r'\b((?:EH|KY|FK|G|ML|PA|KA|TD|DD|AB|IV|PH|KW|HS|ZE)\d+\s*\d*\w*)\b', address, re.I)
    postcode = pc_match.group(1).upper() if pc_match else ''

    return {
        "id": str(prop.get('id', '')),
        "title": prop.get('propertyTypeFullDescription', f"{beds}-bed property"),
        "price": price,
        "price_text": price_text,
        "beds": beds,
        "baths": baths,
        "property_type": (prop.get('propertySubType') or 'property').lower(),
        "address": address,
        "area": address.split(',')[-1].strip() if ',' in address else "",
        "postcode": postcode,
        "description": (prop.get('summary') or '')[:200],
        "url": f"https://www.rightmove.co.uk{prop.get('propertyUrl', '')}",
        "image_url": images[0] if images else "",
        "images": images,
        "features": prop.get('keyFeatures') or [],
        "portal": "rightmove",
        "category": categorize(price, beds),
    }


def main():
    all_props = []
    seen_ids = set()

    for location_identifier in [x.strip() for x in LOCATION_IDENTIFIERS if x.strip()]:
        for page_num in range(MAX_PAGES):
            index = page_num * 24
            html = fetch_page(BEDS, index, location_identifier)
            if not html:
                break

            raw_properties, _ = extract_props_from_html(html)
            if not raw_properties:
                break

            new_this_page = 0
            for prop in raw_properties:
                parsed = parse_property(prop)
                if parsed and parsed['id'] and parsed['id'] not in seen_ids:
                    parsed['search_location_identifier'] = location_identifier
                    seen_ids.add(parsed['id'])
                    all_props.append(parsed)
                    new_this_page += 1

            # Stop early if Rightmove returns a duplicate/end page.
            if new_this_page == 0:
                break

    print(json.dumps({
        "portal": "rightmove",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_props),
        "properties": all_props,
    }, indent=2))


if __name__ == "__main__":
    main()
