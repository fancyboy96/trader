#!/usr/bin/env python3
"""
GDELT scan script for Orbit Defence Intelligence.

Queries the GDELT DOC 2.0 API for SA defence businesses and stores raw
signals in the local SQLite database. Claude extraction is skipped until
an API key is configured in .env.

Usage:
    python3 scripts/gdelt_scan.py           # default 14-day window
    python3 scripts/gdelt_scan.py 30        # 30-day window
"""

import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "orbit.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"

# ---------------------------------------------------------------------------
# Seed businesses — Appendix B of docs/reqs.md
# ---------------------------------------------------------------------------
SEED_BUSINESSES = [
    {"name": "BAE Systems Australia",       "type": "prime_contractor"},
    {"name": "Hanwha Defense Australia",    "type": "prime_contractor"},
    {"name": "ASC Pty Ltd",                 "type": "prime_contractor"},
    {"name": "Thales Australia",            "type": "prime_contractor"},
    {"name": "Saab Australia",              "type": "prime_contractor"},
    {"name": "Boeing Defence Australia",    "type": "prime_contractor"},
    {"name": "Lockheed Martin Australia",   "type": "prime_contractor"},
    {"name": "Raytheon Australia",          "type": "prime_contractor"},
    {"name": "L3Harris Australia",          "type": "prime_contractor"},
    {"name": "NIOA",                        "type": "prime_contractor"},
]

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """Create the DB and apply schema if not already present."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    return conn


def seed_businesses(conn: sqlite3.Connection) -> None:
    """Insert seed businesses that don't already exist."""
    inserted = 0
    for biz in SEED_BUSINESSES:
        existing = conn.execute(
            "SELECT id FROM businesses WHERE name = ?", (biz["name"],)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO businesses (id, name, type, status) VALUES (?, ?, ?, 'active')",
                (str(uuid.uuid4()), biz["name"], biz["type"]),
            )
            inserted += 1
    conn.commit()
    if inserted:
        print(f"Seeded {inserted} new businesses.")


# ---------------------------------------------------------------------------
# GDELT
# ---------------------------------------------------------------------------

def query_gdelt(business_name: str, timespan_days: int, retries: int = 3) -> list[dict]:
    """Fetch articles from GDELT DOC 2.0 API for a given business name."""
    params = {
        "query": f'"{business_name}" defence Australia',
        "mode": "artlist",
        "maxrecords": "25",
        "timespan": f"{timespan_days}d",
        "format": "json",
    }
    url = GDELT_BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "OrbitDefenceIntelligence/0.1"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                return data.get("articles") or []
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"    rate limited, waiting {wait}s ...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"    GDELT error: {e}")
                return []
        except Exception as e:
            print(f"    GDELT error: {e}")
            return []
    return []


def parse_gdelt_date(seendate: str) -> str | None:
    """Convert GDELT date string (20240101T120000Z) to ISO 8601."""
    try:
        return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").isoformat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def run_scan(timespan_days: int = 14) -> None:
    conn = init_db()
    seed_businesses(conn)

    businesses = conn.execute("SELECT id, name FROM businesses").fetchall()

    scan_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO gdelt_scans (id, triggered_by, entities_scanned, timespan_days, status)
           VALUES (?, 'local', ?, ?, 'running')""",
        (scan_id, json.dumps([b["name"] for b in businesses]), timespan_days),
    )
    conn.commit()

    print(f"\nScan ID : {scan_id}")
    print(f"Window  : {timespan_days} days")
    print(f"Entities: {len(businesses)}")
    print("-" * 50)

    total_articles = 0
    new_signals = 0

    for biz in businesses:
        print(f"  {biz['name']} ...", end=" ", flush=True)
        articles = query_gdelt(biz["name"], timespan_days)
        print(f"{len(articles)} articles", flush=True)
        total_articles += len(articles)

        time.sleep(5)  # respect GDELT rate limits

        for article in articles:
            url = article.get("url")
            if not url:
                continue

            # Deduplicate by URL — link to this business even if signal exists
            existing = conn.execute(
                "SELECT id FROM news_signals WHERE url = ?", (url,)
            ).fetchone()

            if existing:
                conn.execute(
                    "INSERT OR IGNORE INTO news_signal_businesses (signal_id, business_id) VALUES (?, ?)",
                    (existing["id"], biz["id"]),
                )
                continue

            signal_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO news_signals
                       (id, headline, url, source_domain, published_at, scan_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    signal_id,
                    article.get("title"),
                    url,
                    article.get("domain"),
                    parse_gdelt_date(article.get("seendate", "")),
                    scan_id,
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO news_signal_businesses (signal_id, business_id) VALUES (?, ?)",
                (signal_id, biz["id"]),
            )
            new_signals += 1

        conn.commit()

    conn.execute(
        """UPDATE gdelt_scans
           SET articles_found = ?, signals_extracted = ?, status = 'complete'
           WHERE id = ?""",
        (total_articles, new_signals, scan_id),
    )
    conn.commit()
    conn.close()

    print("-" * 50)
    print(f"Done.")
    print(f"  Total articles found : {total_articles}")
    print(f"  New signals stored   : {new_signals}")
    print(f"  Database             : {DB_PATH}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    run_scan(days)
