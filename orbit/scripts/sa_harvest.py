#!/usr/bin/env python3
"""
SA Government CKAN contractor/consultant harvester for Orbit Defence Intelligence.

Queries data.sa.gov.au for contractor and consultant datasets published by SA
government agencies, downloads each CSV/XLSX, and stores agencies + contracts
in the local SQLite database.

Usage:
    python3 scripts/sa_harvest.py                        # last 2 FYs (default)
    python3 scripts/sa_harvest.py --all-years            # full history
    python3 scripts/sa_harvest.py --dry-run              # preview, no DB writes
    python3 scripts/sa_harvest.py --org defence-sa       # single CKAN org slug
    python3 scripts/sa_harvest.py --tag contractors      # single tag query
    python3 scripts/sa_harvest.py --min-year 2022        # from FY2022-23 onwards
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

try:
    import warnings
    import openpyxl
    # Suppress openpyxl warnings about unsupported worksheet extensions
    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "orbit.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"
ENTITIES_PATH = ROOT / "data" / "entities.json"

CKAN_BASE = "https://data.sa.gov.au/data/api/3/action"

# ---------------------------------------------------------------------------
# CKAN tag queries
# Notes:
#   - Tags are case-sensitive; 'consultants' and 'Consultants' are different sets.
#   - 'Contractors' (capital C) anomalously matches 120k+ records — omitted.
#   - Single-word stems ('contractor', 'consultant', 'consultancies') also match
#     120k+ records — omitted.
#   - Multi-word tags are quoted in the fq parameter (see fetch_datasets_by_tag).
# ---------------------------------------------------------------------------
SEARCH_TAGS = [
    "contractors",
    "consultants",
    "Consultants",
    "contractors engaged",
    "consultants engaged",
    # NALHN (Northern Adelaide Local Health Network) uses agency-specific tags
    # rather than the generic ones — must be queried explicitly.
    "NALHN Contractors",
    "NALHN Consultants",
]

# Agencies whose contractor datasets are not discoverable via tags above.
# These are queried directly by org slug and filtered to contractor/consultant
# resources in the standard processing pipeline.
# Notes:
#   - tafe-sa: has contractor data but uses an unparseable pivot-table format (years
#     as columns). Excluded until a custom parser is written.
#   - renewal-sa: standard 3-column CSV format, not tagged with any SEARCH_TAGS.
SUPPLEMENTAL_ORGS = [
    "renewal-sa",
]

# Free-text fallback — disabled (returns 800+ noisy results).
SEARCH_TERMS: list[str] = []

# ---------------------------------------------------------------------------
# Row patterns to skip in parse_rows
# ---------------------------------------------------------------------------
SKIP_EXACT = {
    "total", "grand total", "subtotal", "sub total", "name",
    "contractors", "consultants", "contractor", "consultant",
    "various", "nil", "n/a", "consultancies", "n.a.", "na",
}
YEAR_PATTERN = re.compile(r"^\d{4}[-/]\d{2,4}$")
BARE_YEAR_PATTERN = re.compile(r"^20[1-2]\d$")


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
    return " ".join(name.lower().split())


def build_entity_index(entities: list[dict]) -> dict[str, str]:
    index = {}
    for e in entities:
        canon = e["canonical_name"]
        index[normalise(canon)] = canon
        for alias in e.get("aliases", []):
            index[normalise(alias)] = canon
    return index


def match_entity(name: str, index: dict[str, str]) -> str | None:
    return index.get(normalise(name))


# ---------------------------------------------------------------------------
# CKAN API helpers
# ---------------------------------------------------------------------------

def ckan_get(endpoint: str, params: dict) -> dict:
    """Fetch a CKAN API endpoint with retry on rate-limit."""
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    url = f"{CKAN_BASE}/{endpoint}?{qs}"
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


def fetch_datasets_by_tag(tag: str) -> list[dict]:
    """Return all datasets with a given tag."""
    # Quote multi-word tags so Solr treats them as a phrase
    fq_tag = f'tags:"{tag}"' if " " in tag else f"tags:{tag}"
    rows = 100
    start = 0
    results = []
    while True:
        data = ckan_get("package_search", {"fq": fq_tag, "rows": rows, "start": start})
        batch = data.get("result", {}).get("results", [])
        results.extend(batch)
        total = data.get("result", {}).get("count", 0)
        start += rows
        if start >= total or not batch:
            break
        time.sleep(0.5)
    return results


def fetch_org_datasets(org_slug: str) -> list[dict]:
    """All datasets for a specific organisation slug."""
    data = ckan_get("package_search", {"fq": f"organization:{org_slug}", "rows": 500})
    return data.get("result", {}).get("results", [])


def fetch_org_meta(org_slug: str) -> dict:
    """Organisation metadata."""
    data = ckan_get("organization_show", {"id": org_slug, "include_datasets": "false"})
    return data.get("result", {})


def get_all_datasets(org_filter: str | None, tag_filter: str | None) -> list[dict]:
    """Collect unique datasets from all tag queries. Returns deduplicated list."""
    seen: set[str] = set()
    all_datasets: list[dict] = []

    if org_filter:
        print(f"  Fetching datasets for org: {org_filter}", flush=True)
        for ds in fetch_org_datasets(org_filter):
            if ds["id"] not in seen:
                seen.add(ds["id"])
                all_datasets.append(ds)
        return all_datasets

    tags = [tag_filter] if tag_filter else SEARCH_TAGS
    for tag in tags:
        datasets = fetch_datasets_by_tag(tag)
        new = [d for d in datasets if d["id"] not in seen]
        print(f"  tag:{tag:<30} {len(datasets):>3} datasets  (+{len(new)} new)", flush=True)
        for d in new:
            seen.add(d["id"])
            all_datasets.append(d)
        time.sleep(0.3)

    # Supplemental org queries for agencies not discoverable by tags
    if not tag_filter:
        for org_slug in SUPPLEMENTAL_ORGS:
            datasets = fetch_org_datasets(org_slug)
            new = [d for d in datasets if d["id"] not in seen]
            print(f"  org:{org_slug:<30} {len(datasets):>3} datasets  (+{len(new)} new)", flush=True)
            for d in new:
                seen.add(d["id"])
                all_datasets.append(d)
            time.sleep(0.3)

    return all_datasets


# ---------------------------------------------------------------------------
# Value / FY parsing
# ---------------------------------------------------------------------------

def parse_value(raw: str) -> int | None:
    """Parse '$1,234,567' or '26890' → integer. Returns None if unparseable or zero."""
    if not raw:
        return None
    cleaned = re.sub(r"[,$\s]", "", raw.strip())
    cleaned = cleaned.split(".")[0]
    try:
        v = int(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def extract_fy(text: str) -> tuple[int | None, str | None, str | None]:
    """
    Extract financial year from a title, slug, or year-column value.
    Returns (start_year, start_date_ISO, end_date_ISO).
    e.g. '2024-25'  → (2024, '2024-07-01', '2025-06-30')
         '2017/18'  → (2017, '2017-07-01', '2018-06-30')
    """
    m = re.search(r"(\d{4})[_\-/](\d{2,4})", text)
    if not m:
        return None, None, None
    year1 = int(m.group(1))
    y2_str = m.group(2)
    year2 = year1 + 1 if len(y2_str) == 2 else int(y2_str)
    return year1, f"{year1}-07-01", f"{year2}-06-30"


# ---------------------------------------------------------------------------
# Resource detection and fetching
# ---------------------------------------------------------------------------

def resource_file_type(resource: dict) -> str | None:
    """Return 'csv', 'xlsx', or None."""
    url = resource.get("url", "").lower()
    fmt = resource.get("format", "").upper()
    if url.endswith(".xlsx"):
        return "xlsx"
    if url.endswith(".xls"):
        return "xls"  # handled separately — openpyxl can't read .xls
    if fmt in ("CSV", "csv") or url.endswith(".csv"):
        return "csv"
    if fmt in ("XLSX", "XLS", "SPREADSHEET"):
        return "xlsx"
    return None


def is_contractor_resource(resource: dict) -> bool:
    """True if resource is a contractor/consultant CSV or XLSX."""
    ftype = resource_file_type(resource)
    if ftype is None or ftype == "xls":
        return False
    name = (resource.get("name") or resource.get("url", "")).lower()
    url = resource.get("url", "").lower()
    keywords = ("contractor", "consultant", "consultanc")
    return any(k in name or k in url for k in keywords)


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "OrbitDefenceIntelligence/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_csv(url: str) -> list[list[str]]:
    """Download CSV and return rows. Handles Windows line endings and quoted newlines."""
    raw_bytes = download_bytes(url)
    # Wrap in TextIOWrapper with newline='' so csv.reader handles embedded newlines correctly
    text = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8-sig", errors="replace", newline="")
    return list(csv.reader(text))


def fetch_xlsx(url: str) -> list[list[str]]:
    """Download XLSX and return rows as lists of strings."""
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl not installed — run: pip3 install openpyxl")
    raw_bytes = download_bytes(url)
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([str(cell).strip() if cell is not None else "" for cell in row])
    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------

def _is_skip_name(name: str) -> bool:
    """True if a row's name column is a header, summary, or placeholder."""
    nl = name.lower().strip()
    if not nl:
        return True
    if nl in SKIP_EXACT:
        return True
    if YEAR_PATTERN.match(name) or BARE_YEAR_PATTERN.match(name):
        return True
    if nl.startswith("total all ") or nl.startswith("value of "):
        return True
    if "combined" in nl and ("below" in nl or "contractors" in nl or "consultanc" in nl):
        return True
    if "above $10,000" in nl or "below $10,000" in nl:
        return True
    if "above $10 000" in nl or "below $10 000" in nl:
        return True
    return False


def _detect_inverted(rows: list[list[str]]) -> bool:
    """
    Detect 'inverted' column format: year | value | name.
    Used by ESCOSA, Housing Trust, Funds SA, PIRSA, State Opera etc.
    We check if the majority of non-empty first-column values are year strings.
    """
    first_cols = [r[0].strip() for r in rows if r and r[0].strip()][:15]
    if not first_cols:
        return False
    year_hits = sum(
        1 for v in first_cols
        if YEAR_PATTERN.match(v) or BARE_YEAR_PATTERN.match(v)
    )
    return year_hits >= max(2, len(first_cols) * 0.5)


def parse_rows(rows: list[list[str]], resource_fy_year: int | None = None,
               min_year: int | None = None) -> list[dict]:
    """
    Extract (name, purpose, value, fy_year) records from raw spreadsheet rows.

    Handles two column layouts:
      Standard : name    | purpose | value
      Inverted : year    | ???     | ???    (ESCOSA, Housing Trust, Funds SA…)

    For inverted datasets the year column doubles as a per-row FY date.
    The two remaining columns can be in either order (year|name|value or
    year|value|name), so we try both and use whichever produces a valid value.
    """
    inverted = _detect_inverted(rows)
    records = []

    for row in rows:
        row = [c.strip() for c in row]
        # Strip trailing empty cells (some XLSX files have many blank columns at right)
        while row and not row[-1]:
            row.pop()
        while len(row) < 3:
            row.append("")

        if inverted:
            year_col = row[0]
            row_fy_year, row_start, row_end = extract_fy(year_col)

            # Apply per-row year filter before any further processing
            if min_year and row_fy_year is not None and row_fy_year < min_year:
                continue

            # Inverted layout: year | name [| purpose] | value
            # Col 1 is always the name; last col is always the value.
            # Works for both 3-col (year|name|value) and 4-col (year|name|purpose|value).
            name = row[1]
            value_raw = row[-1]
            purpose = row[2] if len(row) >= 4 else ""
        else:
            name = row[0]
            purpose = row[1]
            value_raw = row[-1]
            row_fy_year, row_start, row_end = None, None, None

        value = parse_value(value_raw)

        if _is_skip_name(name):
            continue
        if YEAR_PATTERN.match(name) or BARE_YEAR_PATTERN.match(name):
            continue
        if value is None:
            continue

        # Determine FY dates for this record
        fy_year = row_fy_year or resource_fy_year
        if row_start and row_end:
            start_date, end_date = row_start, row_end
        elif fy_year:
            start_date, end_date = f"{fy_year}-07-01", f"{fy_year + 1}-06-30"
        else:
            start_date, end_date = None, None

        records.append({
            "name": name,
            "purpose": purpose,
            "value": value,
            "value_display": value_raw,
            "fy_year": fy_year,
            "start_date": start_date,
            "end_date": end_date,
        })

    return records


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def upsert_agency(conn: sqlite3.Connection, org: dict) -> None:
    slug = org.get("name", "")
    if not slug:
        return
    existing = conn.execute("SELECT id FROM agencies WHERE slug = ?", (slug,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE agencies SET name = ?, jurisdiction = ?, updated_at = datetime('now')
               WHERE slug = ?""",
            (org.get("title") or org.get("display_name") or slug,
             "Government of South Australia", slug),
        )
        return
    conn.execute(
        """INSERT INTO agencies (id, name, slug, state, jurisdiction)
           VALUES (?, ?, ?, 'SA', 'Government of South Australia')""",
        (str(uuid.uuid4()), org.get("title") or org.get("display_name") or slug, slug),
    )


def upsert_business(conn: sqlite3.Connection, name: str, canonical: str | None) -> str:
    display_name = canonical or name
    existing = conn.execute(
        "SELECT id FROM businesses WHERE name = ?", (display_name,)
    ).fetchone()
    if existing:
        return existing["id"]
    biz_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO businesses (id, name, state, status, type, created_by) VALUES (?, ?, 'SA', 'active', 'other', 'sa_ckan')",
        (biz_id, display_name),
    )
    return biz_id


def make_contract_number(dataset_id: str, name: str, purpose: str, value: int) -> str:
    """Stable synthetic contract number — ensures reruns are idempotent."""
    h = hashlib.md5(f"{dataset_id}|{name}|{purpose}|{value}".encode()).hexdigest()[:12]
    return f"SA-CKAN-{h}"


def store_contract(
    conn: sqlite3.Connection,
    record: dict,
    agency_name: str,
    business_id: str,
    dataset_id: str,
    dataset_title: str,
    resource_name: str,
) -> bool:
    """Insert contract if not already present. Returns True if new."""
    contract_number = make_contract_number(
        dataset_id, record["name"], record["purpose"], record["value"]
    )
    if conn.execute(
        "SELECT id FROM contracts WHERE contract_number = ?", (contract_number,)
    ).fetchone():
        return False

    conn.execute(
        """INSERT INTO contracts
           (id, title, contract_number, status, value_aud, value_display,
            start_date, end_date, contracting_agency, category,
            prime_contractor_id, notes, created_by)
           VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, 'professional_services', ?, ?, 'sa_ckan')""",
        (
            str(uuid.uuid4()),
            record["purpose"] or record["name"],
            contract_number,
            record["value"],
            record["value_display"],
            record.get("start_date"),
            record.get("end_date"),
            agency_name,
            business_id,
            f"{dataset_title} | {resource_name}",
        ),
    )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool, org_filter: str | None, tag_filter: str | None,
        min_year: int | None) -> None:
    conn = None if dry_run else init_db()
    entities = load_entities()
    entity_index = build_entity_index(entities)

    print("\nSA CKAN Harvest")
    print(f"Dry run    : {dry_run}")
    print(f"XLSX       : {'yes' if HAS_OPENPYXL else 'NO — pip3 install openpyxl'}")
    if min_year:
        print(f"Min year   : FY{min_year}-{str(min_year + 1)[-2:]} onwards")
    else:
        print("Min year   : all years")
    print(f"Entities   : {len(entity_index)}")
    print("-" * 60)

    print("\nCollecting datasets ...")
    datasets = get_all_datasets(org_filter, tag_filter)
    print(f"\nTotal unique datasets: {len(datasets)}")

    org_cache: dict[str, dict] = {}
    total_resources = 0
    skipped_year = 0
    skipped_format = 0
    new_contracts = 0
    known_matches = 0
    unmatched: dict[str, int] = {}

    print("\nProcessing datasets ...")
    for ds in datasets:
        ds_title = ds.get("title", ds.get("name", ""))
        org_name = ds.get("organization", {}).get("title", "") if ds.get("organization") else ""
        org_slug = ds.get("organization", {}).get("name", "") if ds.get("organization") else ""
        resources = ds.get("resources", [])

        # Dataset-level FY (may be None for multi-year datasets)
        ds_fy_year, ds_start, ds_end = extract_fy(ds_title or ds.get("name", ""))

        # Skip whole dataset if we can determine it's entirely outside range
        if min_year and ds_fy_year is not None and ds_fy_year < min_year:
            skipped_year += 1
            continue

        # Upsert agency (fetch org metadata once per slug)
        if org_slug not in org_cache:
            if not dry_run:
                org_meta = fetch_org_meta(org_slug)
                org_cache[org_slug] = org_meta
                upsert_agency(conn, org_meta if org_meta else {"name": org_slug, "title": org_name})
                time.sleep(0.2)
            else:
                org_cache[org_slug] = {}

        contractor_resources = [r for r in resources if is_contractor_resource(r)]

        # Count non-CSV/XLSX contractor resources as skipped
        for r in resources:
            rname = (r.get("name") or r.get("url", "")).lower()
            if any(k in rname for k in ("contractor", "consultant")):
                if resource_file_type(r) == "xls":
                    skipped_format += 1

        if not contractor_resources:
            continue

        print(f"\n  {org_name or org_slug} — {ds_title}", flush=True)

        for resource in contractor_resources:
            res_name = resource.get("name", "")
            url = resource.get("url", "")
            ftype = resource_file_type(resource)

            if not url:
                print(f"    [SKIP] {res_name}: no URL")
                continue

            # Resolve FY at resource level
            res_fy_year = ds_fy_year
            res_start, res_end = ds_start, ds_end
            if res_fy_year is None:
                res_fy_year, res_start, res_end = extract_fy(res_name or url)

            # Per-resource year filter (only when FY is known at resource level)
            if min_year and res_fy_year is not None and res_fy_year < min_year:
                skipped_year += 1
                continue

            total_resources += 1
            fy_label = f"FY{res_fy_year}-{str(res_fy_year + 1)[-2:]}" if res_fy_year else "FY?"
            fmt_label = ftype.upper() if ftype else "?"
            print(f"    [{fy_label}/{fmt_label}] {res_name} ...", end=" ", flush=True)

            try:
                if ftype == "xlsx":
                    rows = fetch_xlsx(url)
                else:
                    rows = fetch_csv(url)
            except Exception as e:
                print(f"SKIP ({e})")
                continue

            records = parse_rows(rows, resource_fy_year=res_fy_year, min_year=min_year)
            print(f"{len(records)} records", end="", flush=True)

            if dry_run:
                print()
                for r in records[:3]:
                    print(f"      {r['name'][:50]:<50}  ${r['value']:>10,}  {r['purpose'][:40]}")
                continue

            added = 0
            for record in records:
                canonical = match_entity(record["name"], entity_index)
                if canonical:
                    known_matches += 1
                else:
                    unmatched[record["name"]] = unmatched.get(record["name"], 0) + 1

                biz_id = upsert_business(conn, record["name"], canonical)
                # Use per-record dates (inverted format) if available, else resource-level
                if not record.get("start_date"):
                    record["start_date"] = res_start
                    record["end_date"] = res_end

                stored = store_contract(
                    conn, record, org_name or org_slug, biz_id,
                    ds["id"], ds_title, res_name,
                )
                if stored:
                    added += 1
                    new_contracts += 1

            print(f"  (+{added} new)")
            time.sleep(0.3)

        if not dry_run:
            conn.commit()

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    print(f"  Datasets found         : {len(datasets)}")
    print(f"  Resources skipped(year): {skipped_year}")
    print(f"  Resources skipped(fmt) : {skipped_format}  (.xls — use xlrd to fix)")
    print(f"  Resources fetched      : {total_resources}")
    print(f"  Known entity matches   : {known_matches}")
    print(f"  New contracts added    : {new_contracts}")

    if not dry_run:
        agency_count = conn.execute("SELECT COUNT(*) FROM agencies").fetchone()[0]
        contract_count = conn.execute(
            "SELECT COUNT(*) FROM contracts WHERE created_by = 'sa_ckan'"
        ).fetchone()[0]
        print(f"  Agencies in DB         : {agency_count}")
        print(f"  SA contracts total     : {contract_count}")
        conn.close()

    if unmatched:
        top = sorted(unmatched.items(), key=lambda x: -x[1])
        print(f"\n  Top unmatched contractors (not in entities.json):")
        for name, count in top[:20]:
            print(f"    {count:>3}x  {name}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    current_fy_start = datetime.now().year if datetime.now().month >= 7 else datetime.now().year - 1
    default_min_year = current_fy_start - 2  # last 2 complete FYs

    parser = argparse.ArgumentParser(description="Harvest SA government CKAN contractor data")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--org", dest="org", help="CKAN org slug (e.g. defence-sa)")
    parser.add_argument("--tag", dest="tag", help="Query a single CKAN tag only")
    parser.add_argument(
        "--min-year", dest="min_year", type=int, default=default_min_year,
        help=f"FY start year lower bound (default: {default_min_year} = last 2 FYs)",
    )
    parser.add_argument(
        "--all-years", action="store_true",
        help="Import all historical data regardless of year",
    )
    args = parser.parse_args()

    min_year = None if args.all_years else args.min_year
    run(dry_run=args.dry_run, org_filter=args.org, tag_filter=args.tag, min_year=min_year)
