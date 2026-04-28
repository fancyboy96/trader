#!/usr/bin/env python3
"""
Export analysis CSVs from the Orbit SQLite database.

Produces:
  data/export_contracts_YYYY-MM-DD.csv   — all contracts with supplier, agency, value, title
  data/export_contractors_YYYY-MM-DD.csv — contractors ranked by contract count and total value

Usage:
    python3 scripts/export_analysis.py
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "orbit.db"


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    run_date = datetime.now().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # 1. Contracts export
    # ------------------------------------------------------------------
    contracts = conn.execute("""
        SELECT
            c.contract_number,
            c.title,
            c.contracting_agency,
            b.name       AS supplier,
            b.abn        AS supplier_abn,
            c.value_aud,
            c.awarded_date,
            c.start_date,
            c.end_date,
            c.procurement_method,
            c.unspsc_code
        FROM contracts c
        LEFT JOIN businesses b ON c.prime_contractor_id = b.id
        ORDER BY c.value_aud DESC
    """).fetchall()

    contracts_path = ROOT / "data" / f"export_contracts_{run_date}.csv"
    with open(contracts_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "contract_number", "title", "agency", "supplier", "supplier_abn",
            "value_aud", "awarded_date", "start_date", "end_date",
            "procurement_method", "unspsc_code"
        ])
        for r in contracts:
            writer.writerow([
                r["contract_number"],
                r["title"],
                r["contracting_agency"],
                r["supplier"],
                r["supplier_abn"],
                r["value_aud"],
                r["awarded_date"],
                r["start_date"],
                r["end_date"],
                r["procurement_method"],
                r["unspsc_code"],
            ])

    print(f"Contracts  : {len(contracts):,} rows → {contracts_path.relative_to(ROOT)}")

    # ------------------------------------------------------------------
    # 2. Contractors summary with year-by-year breakdown
    # ------------------------------------------------------------------

    # Get all distinct years in the data
    years = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT strftime('%Y', awarded_date) AS yr
            FROM contracts
            WHERE awarded_date IS NOT NULL
            ORDER BY yr
        """).fetchall()
    ]

    # Build per-contractor totals
    contractors = conn.execute("""
        SELECT
            b.name,
            b.abn,
            b.state,
            COUNT(c.id)      AS contract_count,
            SUM(c.value_aud) AS total_value,
            MAX(c.value_aud) AS largest_contract,
            MIN(c.awarded_date) AS first_award,
            MAX(c.awarded_date) AS last_award
        FROM businesses b
        JOIN contracts c ON c.prime_contractor_id = b.id
        GROUP BY b.id
        ORDER BY total_value DESC NULLS LAST
    """).fetchall()

    # Build per-contractor per-year value lookup
    yearly_rows = conn.execute("""
        SELECT
            b.id,
            strftime('%Y', c.awarded_date) AS yr,
            SUM(c.value_aud) AS year_value,
            COUNT(c.id)      AS year_count
        FROM businesses b
        JOIN contracts c ON c.prime_contractor_id = b.id
        WHERE c.awarded_date IS NOT NULL
        GROUP BY b.id, yr
    """).fetchall()

    yearly: dict[str, dict] = {}
    for r in yearly_rows:
        yearly.setdefault(r["id"], {})[r["yr"]] = {
            "value": r["year_value"],
            "count": r["year_count"],
        }

    # Get business id for each contractor row
    biz_ids = {
        r["name"]: conn.execute(
            "SELECT id FROM businesses WHERE name = ?", (r["name"],)
        ).fetchone()["id"]
        for r in contractors
    }

    contractors_path = ROOT / "data" / f"export_contractors_{run_date}.csv"
    year_headers = [f"{y}_value" for y in years] + [f"{y}_contracts" for y in years]

    with open(contractors_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "supplier_name", "abn", "state",
            "total_contracts", "total_value_aud",
            "largest_contract_aud", "first_award", "last_award",
            *year_headers,
        ])
        for r in contractors:
            biz_id = biz_ids[r["name"]]
            biz_years = yearly.get(biz_id, {})
            year_values = [biz_years.get(y, {}).get("value", "") for y in years]
            year_counts = [biz_years.get(y, {}).get("count", "") for y in years]
            writer.writerow([
                r["name"],
                r["abn"],
                r["state"],
                r["contract_count"],
                r["total_value"],
                r["largest_contract"],
                r["first_award"],
                r["last_award"],
                *year_values,
                *year_counts,
            ])

    print(f"Contractors: {len(contractors):,} rows → {contractors_path.relative_to(ROOT)}")

    # ------------------------------------------------------------------
    # Quick summary to terminal
    # ------------------------------------------------------------------
    total_value = sum(r["value_aud"] for r in contracts if r["value_aud"])
    print(f"\nSummary:")
    print(f"  Total contracts     : {len(contracts):,}")
    print(f"  Total contract value: ${total_value:,.0f}")
    print(f"  Unique contractors  : {len(contractors):,}")

    print(f"\nTop 10 contractors by total value:")
    for r in contractors[:10]:
        val = f"${r['total_value']:,.0f}" if r["total_value"] else "n/a"
        print(f"  {val:>18}  ({r['contract_count']:>4} contracts)  {r['name']}")

    conn.close()


if __name__ == "__main__":
    run()
