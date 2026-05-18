# UK Property CLI

Agent-friendly UK property search from Rightmove, ESPC and Zoopla with normalised JSON output.

The CLI fetches and normalises listings. Filtering, scoring, dedupe and snapshot comparison are explicit layers on top, not hidden parser magic.

## Install

```bash
git clone https://github.com/abracadabra50/uk-property-cli.git
cd uk-property-cli
python3 -m pip install -e .
```

No runtime Python dependencies. Rightmove and ESPC use `curl` + stdlib. Zoopla uses the optional Firecrawl CLI because of Cloudflare.

## Quick start

```bash
# Search Edinburgh Rightmove flats under £250k
uk-property search --portal rightmove --location edinburgh --min-beds 1 --max-price 250000 --property-types flat

# Search all portals using an external agent/user profile, filter, dedupe and rank
uk-property search --profile ~/property-skills/profiles/example-search.json --apply-filters --rank

# Find portal-specific location IDs
uk-property locations edinburgh

# Deduplicate saved portal outputs
uk-property dedupe cache/espc.json cache/rightmove.json cache/zoopla.json

# Compare snapshots
uk-property compare cache/yesterday.json cache/today.json
```

Old script entrypoints still work:

```bash
python3 parsers/rightmove.py 1 1 REGION^475 250000 flat
./fetch.sh rightmove 1 1 REGION^475 250000 flat
```

## Commands

### `search`

```bash
uk-property search \
  --portal all|rightmove|espc|zoopla \
  --location edinburgh \
  --location-id 'REGION^475' \
  --min-beds 1 \
  --max-price 250000 \
  --property-types flat \
  --max-pages 3 \
  --apply-filters \
  --explain \
  --rank \
  --jsonl
```

### `dedupe`

Dedupe uses confidence scoring. Same-portal listings only merge on matching portal ID/URL. Cross-portal listings merge when address, street tokens, postcode sector, beds and price support it.

The output includes `duplicate_candidates` so fuzzy cases are visible instead of silently merged.

### `filter`

Filters can explain removals:

```bash
uk-property filter results.json --areas EH3,EH9,EH10 --max-price 250000 --explain
```

### `locations`

```bash
uk-property locations edinburgh
```

Returns known portal location identifiers such as Rightmove `REGION^475`.

## Schema

Every listing is normalised to `property-listing.v1`:

```json
{
  "schema_version": "property-listing.v1",
  "id": "174727811",
  "portal": "rightmove",
  "url": "https://www.rightmove.co.uk/properties/...",
  "address": "115/4 Warrender Park Road, Edinburgh, EH9 1EN",
  "price": 210000,
  "price_text": "Offers Over £210,000",
  "beds": 1,
  "baths": 1,
  "property_type": "flat",
  "postcode": "EH9 1EN",
  "images": [],
  "features": [],
  "fetched_at": "2026-05-18T08:00:00+00:00",
  "parser_version": "rightmove-nextjs-v2",
  "fetch_url": "https://www.rightmove.co.uk/..."
}
```

## Profiles and agent skills

The repo deliberately does **not** ship business, household or client-specific profiles.

The CLI is the generic data layer: fetch, normalise, dedupe, filter, compare. Opinionated workflows belong above it — for example in an agent skill, cron job or private profile file.

`--profile` accepts either an explicit JSON path or a local untracked `profiles/<name>.json` file. Keep those outside the public scraper repo when they encode a person, client or operating process.

## Portal support

| Portal | Status | Notes |
| --- | --- | --- |
| Rightmove | Working | Next.js embedded JSON, supports pagination/location/max price/property type |
| ESPC | Working | Edinburgh/Lothians specialist, HTML parsing |
| Zoopla | Optional | Requires Firecrawl CLI/API key |

## Tests

```bash
python3 -m unittest discover tests
python3 -m py_compile $(find uk_property_cli -name '*.py') dedupe.py filter.py compare.py parsers/*.py
```

Live smoke:

```bash
uk-property search --portal rightmove --location edinburgh --min-beds 1 --max-pages 1
```
