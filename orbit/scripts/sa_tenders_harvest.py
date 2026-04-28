#!/usr/bin/env python3
"""
SA Tenders and Contracts portal harvester for Orbit Defence Intelligence.

Scrapes awarded contract data from tenders.sa.gov.au using Playwright.
The site is protected by Cloudflare's JS challenge and individual contract
listings require a registered account.

Flow:
  1. Load /contract/buyerIndex (public) — extract all agency names + buyerIds
  2. Log in using supplier credentials from .env (SA_TENDERS_EMAIL / SA_TENDERS_PASSWORD)
  3. For each agency: scrape /contract/search?buyerId=X&browse=true with pagination
  4. Extract: contract number, supplier, agency, value, dates, procurement method
  5. Store to orbit.db

Why this source:
  Unlike data.sa.gov.au CKAN (which has no dates, no ABNs, no contract numbers),
  tenders.sa.gov.au has real contract numbers, awarded/start/end dates, and buyer IDs —
  enabling much richer entity matching and timeline analysis.

Credentials:
  Create a free Supplier account at https://www.tenders.sa.gov.au/login (Sign Up).
  Then add to .env:
    SA_TENDERS_EMAIL=you@example.com
    SA_TENDERS_PASSWORD=yourpassword

Usage:
    python3 scripts/sa_tenders_harvest.py                    # last 2 FYs (default)
    python3 scripts/sa_tenders_harvest.py --all-years        # full history
    python3 scripts/sa_tenders_harvest.py --dry-run          # preview, no DB writes
    python3 scripts/sa_tenders_harvest.py --headful          # show browser window
    python3 scripts/sa_tenders_harvest.py --max-pages 3      # limit pages per agency
    python3 scripts/sa_tenders_harvest.py --agency "Defence SA"  # single agency
    python3 scripts/sa_tenders_harvest.py --save-html        # dump HTML for debugging
    python3 scripts/sa_tenders_harvest.py --min-year 2023    # from FY2023-24 onwards
    python3 scripts/sa_tenders_harvest.py --list-agencies    # print agency list and exit
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "orbit.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"
ENTITIES_PATH = ROOT / "data" / "entities.json"
ENV_PATH = ROOT / ".env"

BASE_URL = "https://www.tenders.sa.gov.au"
BUYER_INDEX_URL = f"{BASE_URL}/contract/buyerIndex"
LOGIN_URL = f"{BASE_URL}/login"

# Source tag for DB traceability
CREATED_BY = "sa_tenders"

# Pause between page loads
PAGE_DELAY_S = 1.5

# ---------------------------------------------------------------------------
# .env loader (minimal — no dependency on python-dotenv)
# ---------------------------------------------------------------------------


def load_env() -> None:
    """Load key=value pairs from .env into os.environ (if not already set)."""
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


# ---------------------------------------------------------------------------
# DB helpers (shared pattern with sa_harvest.py)
# ---------------------------------------------------------------------------


def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    return conn


def load_entities() -> list[dict]:
    if not ENTITIES_PATH.exists():
        return []
    with open(ENTITIES_PATH) as f:
        return json.load(f)


def normalise(name: str) -> str:
    return " ".join(name.lower().split())


def build_entity_index(entities: list[dict]) -> dict[str, str]:
    index: dict[str, str] = {}
    for e in entities:
        canon = e["canonical_name"]
        index[normalise(canon)] = canon
        for alias in e.get("aliases", []):
            index[normalise(alias)] = canon
    return index


def match_entity(name: str, index: dict[str, str]) -> str | None:
    return index.get(normalise(name))


def upsert_business(conn: sqlite3.Connection, name: str, canonical: str | None) -> str:
    display_name = canonical or name
    existing = conn.execute(
        "SELECT id FROM businesses WHERE name = ?", (display_name,)
    ).fetchone()
    if existing:
        return existing["id"]
    biz_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO businesses (id, name, state, status, type, created_by)"
        " VALUES (?, ?, 'SA', 'active', 'other', ?)",
        (biz_id, display_name, CREATED_BY),
    )
    return biz_id


def store_contract(conn: sqlite3.Connection, record: dict, business_id: str) -> bool:
    """Insert contract if not already present. Returns True if new."""
    cn = record["contract_number"]
    if conn.execute("SELECT 1 FROM contracts WHERE contract_number = ?", (cn,)).fetchone():
        return False
    conn.execute(
        """INSERT INTO contracts
           (id, title, contract_number, status, value_aud, value_display,
            awarded_date, start_date, end_date, contracting_agency,
            procurement_method, category, prime_contractor_id, notes, created_by)
           VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, 'professional_services', ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            record.get("title") or record.get("description") or cn,
            cn,
            record.get("value_aud"),
            record.get("value_display"),
            record.get("awarded_date"),
            record.get("start_date"),
            record.get("end_date"),
            record.get("agency"),
            record.get("procurement_method"),
            business_id,
            record.get("notes"),
            CREATED_BY,
        ),
    )
    return True


# ---------------------------------------------------------------------------
# Value / date parsing
# ---------------------------------------------------------------------------


def parse_value(raw: str) -> int | None:
    if not raw:
        return None
    cleaned = re.sub(r"[,$\s]", "", raw.strip())
    cleaned = cleaned.split(".")[0]
    try:
        v = int(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def parse_date(raw: str) -> str | None:
    """Parse Australian date formats → ISO 8601."""
    if not raw:
        return None
    raw = raw.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", raw)
    if m:
        d, mon_str, y = m.groups()
        mon = months.get(mon_str[:3].lower())
        if mon:
            return f"{y}-{mon}-{int(d):02d}"
    return None


def fy_year_from_date(iso_date: str | None) -> int | None:
    """Return FY start year (July-based) from an ISO date string."""
    if not iso_date:
        return None
    m = re.match(r"^(\d{4})-(\d{2})", iso_date)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    return year if month >= 7 else year - 1


def clean(t: str | None) -> str:
    if not t:
        return ""
    return " ".join(t.split()).strip()


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------


def wait_for_cf(page, timeout_s: int = 20) -> None:
    """Wait out a Cloudflare JS challenge if one is present."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        title = page.title().lower()
        if "just a moment" in title or "attention required" in title:
            print("  [CF challenge in progress …]", flush=True)
            time.sleep(2)
            continue
        cf = page.query_selector("#cf-spinner, #cf-browser-verification, .cf-browser-verification")
        if cf:
            print("  [CF widget detected, waiting …]", flush=True)
            time.sleep(2)
            continue
        break


def goto(page, url: str) -> bool:
    """Navigate to url, wait for domcontentloaded, then handle CF. Returns True on success."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        wait_for_cf(page)
        return True
    except PWTimeout:
        print(f"  [timeout: {url}]", flush=True)
        return False


def save_html(page, label: str) -> None:
    debug_dir = ROOT / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = debug_dir / f"sa_tenders_{label}_{ts}.html"
    path.write_text(page.content(), encoding="utf-8")
    print(f"  [HTML → {path.relative_to(ROOT)}]", flush=True)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def login(page, email: str, password: str) -> bool:
    """
    Log in as a supplier. Returns True on success.
    Uses the Supplier Login tab (username = #supplierUsername).
    """
    print(f"\nLogging in as {email} …", flush=True)
    if not goto(page, LOGIN_URL):
        return False
    time.sleep(0.5)

    # Make sure we're on the supplier tab (it's the default)
    tab = page.query_selector("a[href='#supplier'], button[data-bs-target='#supplier'], li[data-target='#supplier'] a")
    if tab:
        tab.click()
        time.sleep(0.3)

    try:
        page.fill("#supplierUsername", email)
        page.fill("#supplierPassword", password)
        page.click("form:has(#supplierPassword) button[type='submit'], form:has(#supplierPassword) input[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
        wait_for_cf(page)
        time.sleep(1)
    except Exception as e:
        print(f"  [login form error: {e}]", flush=True)
        return False

    # Check if we're still on login page (failed login) or elsewhere (success)
    if "/login" in page.url:
        # Check for error message
        err = page.query_selector(".error, .alert-danger, .invalid-feedback")
        msg = clean(err.inner_text()) if err else "(no error message)"
        print(f"  [login failed: {msg}]", flush=True)
        return False

    print(f"  Logged in. Now at: {page.url}", flush=True)
    return True


# ---------------------------------------------------------------------------
# Buyer index parser
# ---------------------------------------------------------------------------


def get_buyer_index(page, agency_filter: str | None) -> list[dict]:
    """
    Scrape /contract/buyerIndex for the full agency list.
    Returns list of {name, buyer_id, contract_count, url}.
    Optionally filtered by agency name substring.
    """
    print("\nFetching buyer index …", flush=True)
    if not goto(page, BUYER_INDEX_URL):
        print("  [failed to load buyer index]")
        return []

    agencies = []
    links = page.query_selector_all("a[href*='/contract/search?buyerId=']")
    for link in links:
        href = link.get_attribute("href") or ""
        text = clean(link.inner_text())

        # Extract buyerId
        m = re.search(r"buyerId=(\d+)", href)
        if not m:
            continue
        buyer_id = m.group(1)

        # Extract contract count from "(N)" suffix
        count_m = re.search(r"\((\d+)\)\s*$", text)
        count = int(count_m.group(1)) if count_m else 0
        name = re.sub(r"\s*\(\d+\)\s*$", "", text).strip()

        if agency_filter and agency_filter.lower() not in name.lower():
            continue

        url = BASE_URL + href if href.startswith("/") else href
        agencies.append({"name": name, "buyer_id": buyer_id, "count": count, "url": url})

    print(f"  Found {len(agencies)} agencies", flush=True)
    return agencies


# ---------------------------------------------------------------------------
# Contract page scraper
# ---------------------------------------------------------------------------


def detect_columns(headers: list[str]) -> dict[str, int | None]:
    """Map semantic column names to indices from a list of lowercase header strings."""
    def idx(*candidates) -> int | None:
        for cand in candidates:
            for i, h in enumerate(headers):
                if cand in h:
                    return i
        return None

    return {
        "number":   idx("contract no", "contract number", "ref no", "reference no", "number"),
        "title":    idx("title", "description", "subject", "contract title"),
        "supplier": idx("supplier", "contractor", "vendor", "company"),
        "agency":   idx("agency", "buyer", "organisation", "organization", "entity", "buyer name"),
        "value":    idx("value", "amount", "contract value", "$ value"),
        "awarded":  idx("award date", "awarded date", "awarded", "contract award"),
        "start":    idx("start", "commencement", "commence date"),
        "end":      idx("end date", "expiry", "expiration", "completion"),
        "method":   idx("method", "procurement method", "tender type", "process"),
    }


def extract_table_records(page, agency_name: str) -> list[dict]:
    """
    Extract contract records from the HTML table on the current page.
    Returns a list of record dicts.
    """
    records = []

    # Try progressively broader table selectors
    for sel in [
        "table.search-results",
        "table.contracts-table",
        "table.tendersList",
        "#results table",
        ".search-results table",
        "table.table",
        "table",
    ]:
        table = page.query_selector(sel)
        if table:
            break
    else:
        return records

    # Parse headers
    headers: list[str] = []
    header_row = table.query_selector("thead tr") or table.query_selector("tr:first-child")
    if header_row:
        cells = header_row.query_selector_all("th, td")
        headers = [clean(c.inner_text()).lower() for c in cells]

    cols = detect_columns(headers)

    def cell_text(cells: list, idx: int | None) -> str:
        if idx is None or idx >= len(cells):
            return ""
        return clean(cells[idx].inner_text())

    # Data rows
    body = table.query_selector("tbody") or table
    rows = body.query_selector_all("tr")

    for row in rows:
        cells = row.query_selector_all("td")
        if not cells:
            continue  # skip header rows

        # Try to find a detail link in the first few cells
        detail_url = None
        for c in cells[:4]:
            a = c.query_selector("a")
            if a:
                href = a.get_attribute("href") or ""
                if href and "/contract/" in href:
                    detail_url = (BASE_URL + href) if href.startswith("/") else href
                    break

        raw_number   = cell_text(cells, cols["number"])
        raw_title    = cell_text(cells, cols["title"])
        raw_supplier = cell_text(cells, cols["supplier"])
        raw_agency   = cell_text(cells, cols["agency"]) or agency_name
        raw_value    = cell_text(cells, cols["value"])
        raw_awarded  = cell_text(cells, cols["awarded"])
        raw_start    = cell_text(cells, cols["start"])
        raw_end      = cell_text(cells, cols["end"])
        raw_method   = cell_text(cells, cols["method"])

        # Positional fallback if headers weren't detected
        if not headers and len(cells) >= 4:
            raw_number   = cell_text(cells, 0)
            raw_title    = cell_text(cells, 1)
            raw_supplier = cell_text(cells, 2)
            raw_value    = cell_text(cells, 3)
            raw_awarded  = cell_text(cells, 4) if len(cells) > 4 else ""

        # Skip blank or header-like rows
        if not raw_supplier and not raw_number and not raw_title:
            continue
        skip_values = {"supplier", "contractor", "vendor", "company", "name"}
        if raw_supplier.lower() in skip_values:
            continue

        # Build contract number
        if raw_number:
            contract_number = f"SA-TENDERS-{re.sub(r'[^A-Z0-9a-z]', '', raw_number)}"
        else:
            h = hashlib.md5(
                f"{raw_supplier}|{raw_title}|{raw_agency}|{raw_value}|{raw_awarded}".encode()
            ).hexdigest()[:12]
            contract_number = f"SA-TENDERS-{h}"

        records.append({
            "contract_number":   contract_number,
            "title":             raw_title or raw_number,
            "supplier":          raw_supplier,
            "agency":            raw_agency,
            "value_aud":         parse_value(raw_value),
            "value_display":     raw_value or None,
            "awarded_date":      parse_date(raw_awarded),
            "start_date":        parse_date(raw_start),
            "end_date":          parse_date(raw_end),
            "procurement_method": raw_method or None,
            "detail_url":        detail_url,
            "notes":             None,
        })

    return records


def get_next_url(page) -> str | None:
    """Return absolute URL of the next pagination page, or None."""
    for sel in [
        "a:has-text('Next')",
        "a.next",
        "a[rel='next']",
        "a:has-text('>')",
        "a:has-text('»')",
        ".pagination li:last-child a",
    ]:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href")
                if href and href != "#":
                    return (BASE_URL + href) if href.startswith("/") else href
        except Exception:
            pass
    # Disabled/active next indicator → we're done
    if page.query_selector("li.next.disabled, span.next, .pagination .disabled"):
        return None
    return None


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------


def run(
    dry_run: bool,
    headful: bool,
    min_year: int | None,
    max_pages: int | None,
    agency_filter: str | None,
    list_agencies: bool,
    do_save_html: bool,
) -> None:
    if not HAS_PLAYWRIGHT:
        print("ERROR: playwright not installed.")
        print("  pip3 install playwright && playwright install chromium")
        return

    load_env()
    email = os.environ.get("SA_TENDERS_EMAIL", "")
    password = os.environ.get("SA_TENDERS_PASSWORD", "")

    needs_login = not list_agencies and (not email or not password)
    if needs_login:
        print("NOTE: SA_TENDERS_EMAIL / SA_TENDERS_PASSWORD not set.")
        print("      Will attempt unauthenticated scraping first.")
        print("      If the site redirects to /login, add credentials to .env:")
        print("        SA_TENDERS_EMAIL=you@example.com")
        print("        SA_TENDERS_PASSWORD=yourpassword")
        print("      (As of Apr 2026 the site has a temporary bug requiring login.")
        print("       Expected fix: 17 Apr 2026)")

    conn = None if dry_run else init_db()
    entities = load_entities()
    entity_index = build_entity_index(entities)

    print("\nSA Tenders Harvest (Playwright)")
    print(f"Dry run    : {dry_run}")
    print(f"Headful    : {headful}")
    fy_label = f"FY{min_year}-{str(min_year + 1)[-2:]}" if min_year else "all years"
    print(f"Min year   : {fy_label}")
    print(f"Max pages  : {max_pages if max_pages else 'unlimited'}")
    print(f"Agency     : {agency_filter or 'all'}")
    print(f"Entities   : {len(entity_index)}")
    print("-" * 60)

    total_new = 0
    skipped_year = 0
    known_matches = 0
    unmatched: dict[str, int] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not headful,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-AU",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        # --- Step 1: Buyer index (public) ---
        agencies = get_buyer_index(page, agency_filter)
        if not agencies:
            print("No agencies found. Exiting.")
            browser.close()
            return

        if list_agencies:
            print("\nAgencies on tenders.sa.gov.au:")
            for a in sorted(agencies, key=lambda x: x["name"]):
                print(f"  {a['count']:>4}  {a['name']}  (buyerId={a['buyer_id']})")
            browser.close()
            return

        # --- Step 2: Login (if credentials provided) ---
        logged_in = False
        if email and password:
            logged_in = login(page, email, password)
            if not logged_in:
                print("\nERROR: Login failed. Check credentials in .env.")
                if do_save_html:
                    save_html(page, "login_fail")
                browser.close()
                return
        else:
            print("\nProceeding without login (will fail if site requires auth).", flush=True)

        # --- Step 3: Scrape each agency ---
        for agency in agencies:
            agency_name = agency["name"]
            print(f"\n{'─' * 60}", flush=True)
            print(f"  {agency_name}  ({agency['count']} contracts)", flush=True)

            current_url = agency["url"]
            page_num = 0
            agency_new = 0

            while True:
                page_num += 1
                if max_pages and page_num > max_pages:
                    print(f"  [--max-pages {max_pages} reached]")
                    break

                if not goto(page, current_url):
                    print(f"  [failed to load page {page_num}]")
                    break

                # Re-login if we got bounced to login page
                if "/login" in page.url:
                    if email and password:
                        print("  [session expired — re-logging in]", flush=True)
                        if not login(page, email, password):
                            print("  [re-login failed — stopping]")
                            break
                        if not goto(page, current_url):
                            break
                    else:
                        print(
                            "\n  [redirected to /login — site requires auth]\n"
                            "  Add SA_TENDERS_EMAIL and SA_TENDERS_PASSWORD to .env\n"
                            "  and re-run. Expected site fix: 17 Apr 2026."
                        )
                        browser.close()
                        if conn:
                            conn.close()
                        return

                if do_save_html:
                    save_html(page, f"{agency['buyer_id']}_p{page_num}")

                records = extract_table_records(page, agency_name)
                print(f"  page {page_num}: {len(records)} records", flush=True)

                if not records and page_num == 1:
                    print("  [no records found — check --save-html for page HTML]")
                    break

                if not records:
                    break

                for rec in records:
                    supplier = rec.get("supplier", "")
                    if not supplier:
                        continue

                    # Year filter
                    ref_date = rec.get("awarded_date") or rec.get("start_date")
                    fy = fy_year_from_date(ref_date)
                    if min_year and fy is not None and fy < min_year:
                        skipped_year += 1
                        continue

                    if dry_run:
                        val_str = f"${rec['value_aud']:,}" if rec.get("value_aud") else "?"
                        print(
                            f"    {supplier[:50]:<50}  {val_str:>12}  "
                            f"{rec.get('awarded_date', '')}"
                        )
                        continue

                    canonical = match_entity(supplier, entity_index)
                    if canonical:
                        known_matches += 1
                    else:
                        unmatched[supplier] = unmatched.get(supplier, 0) + 1

                    biz_id = upsert_business(conn, supplier, canonical)
                    stored = store_contract(conn, rec, biz_id)
                    if stored:
                        agency_new += 1
                        total_new += 1

                if not dry_run:
                    conn.commit()

                next_url = get_next_url(page)
                if not next_url:
                    break
                current_url = next_url
                time.sleep(PAGE_DELAY_S)

            if not dry_run:
                print(f"  → +{agency_new} new contracts stored")

        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    print(f"  Records skipped (year) : {skipped_year}")
    print(f"  Known entity matches   : {known_matches}")
    print(f"  New contracts added    : {total_new}")

    if not dry_run and conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM contracts WHERE created_by = ?", (CREATED_BY,)
        ).fetchone()[0]
        print(f"  SA Tenders total in DB : {count}")
        conn.close()

    if unmatched:
        top = sorted(unmatched.items(), key=lambda x: -x[1])
        print("\n  Top unmatched contractors (not in entities.json):")
        for name, count in top[:20]:
            print(f"    {count:>3}x  {name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    current_fy = datetime.now().year if datetime.now().month >= 7 else datetime.now().year - 1
    default_min_year = current_fy - 2  # last 2 complete FYs

    parser = argparse.ArgumentParser(
        description="Harvest SA Tenders and Contracts portal via Playwright"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--headful", action="store_true", help="Show browser window")
    parser.add_argument(
        "--min-year", dest="min_year", type=int, default=default_min_year,
        help=f"FY start year lower bound (default: {default_min_year})",
    )
    parser.add_argument(
        "--all-years", action="store_true",
        help="Import all historical data regardless of year",
    )
    parser.add_argument(
        "--max-pages", dest="max_pages", type=int, default=None,
        help="Stop after N pages per agency (for testing)",
    )
    parser.add_argument(
        "--agency", dest="agency", default=None,
        help="Filter to agencies whose name contains this string",
    )
    parser.add_argument(
        "--list-agencies", action="store_true",
        help="Print agency list from buyerIndex and exit (no login required)",
    )
    parser.add_argument(
        "--save-html", dest="save_html", action="store_true",
        help="Save HTML snapshots to data/debug/ for inspection",
    )
    args = parser.parse_args()

    min_year = None if args.all_years else args.min_year
    run(
        dry_run=args.dry_run,
        headful=args.headful,
        min_year=min_year,
        max_pages=args.max_pages,
        agency_filter=args.agency,
        list_agencies=args.list_agencies,
        do_save_html=args.save_html,
    )
