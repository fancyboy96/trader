#!/usr/bin/env python3
"""
AusTender contract harvester for Orbit Defence Intelligence.

Queries the AusTender OCDS API for defence-related contracts, extracts
supplier (company) and contract data, matches suppliers against known
entities, and stores everything in the local SQLite database.

Usage:
    python3 scripts/austender_harvest.py                      # last 90 days
    python3 scripts/austender_harvest.py --days 365           # last year
    python3 scripts/austender_harvest.py --from 2024-01-01    # from a specific date
    python3 scripts/austender_harvest.py --dry-run            # preview only, no DB writes
"""

import argparse
import csv
import json
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "orbit.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"
ENTITIES_PATH = ROOT / "data" / "entities.json"

OCDS_BASE = "https://api.tenders.gov.au/ocds"

# ---------------------------------------------------------------------------
# Defence agency keywords — used to filter out non-defence contracts
# ---------------------------------------------------------------------------
DEFENCE_KEYWORDS = [
    "department of defence",
    "defence housing",
    "australian signals directorate",
    "casg",
    "dst group",
    "defence science",
    "australian war memorial",
    "asd ",
]


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    return conn


# ---------------------------------------------------------------------------
# Entity matching
# ---------------------------------------------------------------------------

def load_entities() -> list[dict]:
    if not ENTITIES_PATH.exists():
        return []
    with open(ENTITIES_PATH) as f:
        return json.load(f)


def normalise(name: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return " ".join(name.lower().split())


def build_entity_index(entities: list[dict]) -> dict[str, str]:
    """
    Returns a dict of normalised_name → canonical_name covering
    canonical names and all aliases.
    """
    index = {}
    for e in entities:
        canon = e["canonical_name"]
        index[normalise(canon)] = canon
        for alias in e.get("aliases", []):
            index[normalise(alias)] = canon
    return index


def match_entity(supplier_name: str, index: dict[str, str]) -> str | None:
    """Return canonical name if supplier matches a known entity, else None."""
    return index.get(normalise(supplier_name))


# ---------------------------------------------------------------------------
# OCDS API fetch with pagination
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "OrbitDefenceIntelligence/0.1"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  [rate limit, waiting {wait}s]", flush=True)
                time.sleep(wait)
            else:
                raise
    return {}


def fetch_pages(start: datetime, end: datetime, max_pages: int = 0):
    """
    Generator — yields (page_number, releases) one page at a time.
    Commits can happen between pages so progress is never lost on interruption.
    """
    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{OCDS_BASE}/findByDates/contractPublished/{start_str}/{end_str}"

    page = 1
    while url:
        if max_pages and page > max_pages:
            print(f"  Reached --max-pages limit ({max_pages}), stopping.")
            break

        print(f"  Page {page} ...", end=" ", flush=True)
        data = fetch_page(url)
        batch = data.get("releases", [])
        print(f"{len(batch)} records", flush=True)

        if not batch:
            break

        yield page, batch

        next_url = data.get("links", {}).get("next")
        url = next_url if next_url and next_url != data.get("links", {}).get("self") else None
        page += 1
        if url:
            time.sleep(1)


# ---------------------------------------------------------------------------
# Parse OCDS release
# ---------------------------------------------------------------------------

def is_defence(release: dict) -> bool:
    for party in release.get("parties", []):
        if "procuringEntity" in party.get("roles", []):
            name = party.get("name", "").lower()
            if any(k in name for k in DEFENCE_KEYWORDS):
                return True
    return False


def parse_release(release: dict) -> dict | None:
    """Extract the fields we care about from an OCDS release."""

    buyer = next(
        (p for p in release.get("parties", []) if "procuringEntity" in p.get("roles", [])),
        {},
    )
    suppliers = [p for p in release.get("parties", []) if "supplier" in p.get("roles", [])]
    contract = release.get("contracts", [{}])[0]
    award = release.get("awards", [{}])[0]

    def get_abn(party: dict) -> str | None:
        for ident in party.get("additionalIdentifiers", []):
            if ident.get("scheme") == "AU-ABN":
                return ident["id"]
        return None

    # UNSPSC code from first contract item
    items = contract.get("items", [])
    unspsc = items[0].get("classification", {}).get("id") if items else None

    return {
        "ocid": release.get("ocid"),
        "contract_number": contract.get("id"),
        "title": contract.get("description") or contract.get("title"),
        "agency": buyer.get("name"),
        "awarded_date": (award.get("date") or "")[:10] or None,
        "start_date": (contract.get("period", {}).get("startDate") or "")[:10] or None,
        "end_date": (contract.get("period", {}).get("endDate") or "")[:10] or None,
        "value_aud": contract.get("value", {}).get("amount"),
        "procurement_method": release.get("tender", {}).get("procurementMethod"),
        "unspsc_code": unspsc,
        "suppliers": [
            {
                "name": s.get("name", ""),
                "abn": get_abn(s),
                "address": s.get("address", {}),
            }
            for s in suppliers
        ],
    }


# ---------------------------------------------------------------------------
# Store to DB
# ---------------------------------------------------------------------------

def upsert_business(conn: sqlite3.Connection, supplier: dict, matched_canonical: str | None) -> str:
    """Insert supplier as a business if not already present. Returns business id."""
    name = matched_canonical or supplier["name"]
    abn = supplier.get("abn")

    # Check by ABN first (most reliable identifier)
    if abn:
        existing = conn.execute("SELECT id FROM businesses WHERE abn = ?", (abn,)).fetchone()
        if existing:
            return existing["id"]

    # Fall back to name match
    existing = conn.execute("SELECT id FROM businesses WHERE name = ?", (name,)).fetchone()
    if existing:
        return existing["id"]

    address = supplier.get("address", {})
    biz_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO businesses (id, name, abn, state, status, type, created_by)
           VALUES (?, ?, ?, ?, 'active', 'other', 'austender')""",
        (biz_id, name, abn, address.get("region", "")),
    )
    return biz_id


def store_contract(conn: sqlite3.Connection, parsed: dict, supplier_ids: list[str]) -> str | None:
    """Insert contract if not already present. Returns contract id or None if duplicate."""
    if not parsed["contract_number"]:
        return None

    existing = conn.execute(
        "SELECT id FROM contracts WHERE contract_number = ?", (parsed["contract_number"],)
    ).fetchone()
    if existing:
        return None

    # Use first supplier as prime contractor
    prime_id = supplier_ids[0] if supplier_ids else None

    contract_id = str(uuid.uuid4())
    value = parsed["value_aud"]
    try:
        value_int = int(float(value)) if value else None
    except (ValueError, TypeError):
        value_int = None

    conn.execute(
        """INSERT INTO contracts
           (id, title, contract_number, status, value_aud, awarded_date,
            start_date, end_date, contracting_agency, procurement_method,
            unspsc_code, prime_contractor_id, created_by)
           VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, 'austender')""",
        (
            contract_id,
            parsed["title"],
            parsed["contract_number"],
            value_int,
            parsed["awarded_date"],
            parsed["start_date"],
            parsed["end_date"],
            parsed["agency"],
            parsed["procurement_method"],
            parsed["unspsc_code"],
            prime_id,
        ),
    )

    # Insert subcontractors (remaining suppliers)
    for sub_id in supplier_ids[1:]:
        conn.execute(
            "INSERT OR IGNORE INTO contract_subcontractors (contract_id, business_id) VALUES (?, ?)",
            (contract_id, sub_id),
        )

    return contract_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(start: datetime, end: datetime, dry_run: bool = False) -> None:
    conn = init_db() if not dry_run else None
    entities = load_entities()
    entity_index = build_entity_index(entities)

    print(f"\nAusTender Harvest")
    print(f"From    : {start.date()}")
    print(f"To      : {end.date()}")
    print(f"Dry run : {dry_run}")
    print(f"Entities in index: {len(entity_index)}")
    print("-" * 50)

    print("\nFetching and processing releases from AusTender OCDS API ...")

    known_matches = 0
    new_businesses = 0
    new_contracts = 0
    total_fetched = 0
    unmatched_suppliers: dict[str, dict] = {}  # name → {count, abn}

    for page, releases in fetch_pages(start, end, max_pages=args.max_pages):
        total_fetched += len(releases)

        for release in releases:
            parsed = parse_release(release)
            if not parsed:
                continue

            supplier_ids = []

            for supplier in parsed["suppliers"]:
                canonical = match_entity(supplier["name"], entity_index)
                if canonical:
                    known_matches += 1
                else:
                    key = supplier["name"]
                    if key not in unmatched_suppliers:
                        unmatched_suppliers[key] = {"count": 0, "abn": supplier.get("abn")}
                    unmatched_suppliers[key]["count"] += 1

                if dry_run:
                    supplier_ids.append("dry-run-id")
                    continue

                biz_id = upsert_business(conn, supplier, canonical)
                supplier_ids.append(biz_id)

            if not dry_run:
                contract_id = store_contract(conn, parsed, supplier_ids)
                if contract_id:
                    new_contracts += 1

        # Commit after every page so progress is never lost
        if not dry_run:
            conn.commit()

    print(f"Total releases fetched : {total_fetched:,}")

    if not dry_run:
        new_businesses = conn.execute(
            "SELECT COUNT(*) FROM businesses WHERE created_by IS NULL OR created_by = 'austender'"
        ).fetchone()[0]
        conn.commit()
        conn.close()

    print(f"\nResults:")
    print(f"  Known entity matches : {known_matches}")
    print(f"  New businesses added : {new_businesses}")
    print(f"  New contracts added  : {new_contracts}")

    if unmatched_suppliers:
        top = sorted(unmatched_suppliers.items(), key=lambda x: -x[1]["count"])
        print(f"\n  Top unmatched suppliers (not in entities.json):")
        for name, meta in top[:20]:
            print(f"    {meta['count']:>3}x  {name}  ({meta['abn'] or 'no ABN'})")

        # Write full unmatched list to CSV for review
        run_date = datetime.now().strftime("%Y-%m-%d")
        csv_path = ROOT / "data" / f"unmatched_suppliers_{run_date}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["supplier_name", "abn", "contract_count"])
            for name, meta in top:
                writer.writerow([name, meta["abn"] or "", meta["count"]])
        print(f"\n  Full unmatched list written to: {csv_path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harvest AusTender defence contracts")
    parser.add_argument("--days", type=int, default=90, help="Number of days back from today (default: 90)")
    parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--max-pages", type=int, default=0, help="Limit pages fetched (0 = no limit). Each page = 100 records.")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.from_date:
        start_dt = datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
    else:
        start_dt = now - timedelta(days=args.days)

    end_dt = datetime.fromisoformat(args.to_date).replace(tzinfo=timezone.utc) if args.to_date else now

    run(start=start_dt, end=end_dt, dry_run=args.dry_run)
