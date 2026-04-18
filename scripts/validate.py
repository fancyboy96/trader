"""
Data validation script. Run after refresh.py to verify that fetched data
is internally consistent and within plausible ranges.

Usage:
    python scripts/validate.py              # validate all tickers
    python scripts/validate.py NVDA AAPL   # validate specific tickers
    python scripts/validate.py --fail-fast  # stop on first failure

Exit code 0 = all checks passed. Exit code 1 = one or more failures.
"""

import sys
import argparse
from datetime import date, timedelta
from db import get_conn, init_db

PASS = "✓"
FAIL = "✗"
WARN = "⚠"


class Results:
    def __init__(self):
        self.checks = []

    def ok(self, ticker, check, detail=""):
        self.checks.append((ticker, PASS, check, detail))

    def fail(self, ticker, check, detail=""):
        self.checks.append((ticker, FAIL, check, detail))

    def warn(self, ticker, check, detail=""):
        self.checks.append((ticker, WARN, check, detail))

    @property
    def failures(self):
        return [c for c in self.checks if c[1] == FAIL]

    @property
    def warnings(self):
        return [c for c in self.checks if c[1] == WARN]


def validate_fundamentals(conn, ticker: str, r: Results, fail_fast: bool):
    f = conn.execute("""
        SELECT * FROM fundamentals
        WHERE ticker = ?
        ORDER BY snapshot_date DESC LIMIT 1
    """, (ticker,)).fetchone()

    if not f:
        r.fail(ticker, "fundamentals_exist", "no fundamentals row found")
        return

    today = date.today().isoformat()
    age_days = (date.fromisoformat(today) - date.fromisoformat(f["snapshot_date"])).days

    # Freshness
    if age_days <= 7:
        r.ok(ticker, "fundamentals_fresh", f"snapshot {f['snapshot_date']} ({age_days}d ago)")
    elif age_days <= 30:
        r.warn(ticker, "fundamentals_fresh", f"snapshot {f['snapshot_date']} ({age_days}d ago) — consider refreshing")
    else:
        r.fail(ticker, "fundamentals_fresh", f"snapshot {f['snapshot_date']} ({age_days}d ago) — stale")

    if fail_fast and r.failures: return

    # Market cap: must be positive
    if f["market_cap"] and f["market_cap"] > 0:
        r.ok(ticker, "market_cap_positive", f"${f['market_cap']/1e9:.1f}B")
    else:
        r.fail(ticker, "market_cap_positive", f"got {f['market_cap']}")

    # Revenue: must be positive
    if f["revenue_ttm"] and f["revenue_ttm"] > 0:
        r.ok(ticker, "revenue_positive", f"${f['revenue_ttm']/1e9:.2f}B")
    else:
        r.fail(ticker, "revenue_positive", f"got {f['revenue_ttm']}")

    if fail_fast and r.failures: return

    # Gross margin: between 0 and 1
    gm = f["gross_margin"]
    if gm is None:
        r.warn(ticker, "gross_margin_range", "null")
    elif 0 < gm <= 1:
        r.ok(ticker, "gross_margin_range", f"{gm*100:.1f}%")
    else:
        r.fail(ticker, "gross_margin_range", f"out of range: {gm} (expected 0–1; yfinance debtToEquity divide-by-100 bug?)")

    # Debt/equity: non-negative (0 is fine — no debt)
    de = f["debt_to_equity"]
    if de is None:
        r.warn(ticker, "debt_to_equity_range", "null")
    elif 0 <= de <= 20:
        r.ok(ticker, "debt_to_equity_range", f"{de:.2f}x")
    elif de > 20:
        r.warn(ticker, "debt_to_equity_range", f"{de:.2f}x — unusually high")
    else:
        r.fail(ticker, "debt_to_equity_range", f"negative D/E: {de}")

    if fail_fast and r.failures: return

    # Consistency: price_to_fcf ≈ market_cap / free_cashflow
    mcap = f["market_cap"]
    fcf  = f["free_cashflow"]
    stored_pfcf = f["price_to_fcf"]
    if mcap and fcf and fcf > 0 and stored_pfcf:
        computed = mcap / fcf
        delta = abs(computed - stored_pfcf) / stored_pfcf
        if delta < 0.01:
            r.ok(ticker, "price_to_fcf_consistent", f"stored {stored_pfcf:.1f} ≈ computed {computed:.1f}")
        else:
            r.fail(ticker, "price_to_fcf_consistent",
                   f"stored {stored_pfcf:.1f} vs computed {computed:.1f} ({delta*100:.1f}% delta)")

    # Consistency: gross_margin ≈ gross_profit / revenue
    gp  = f["gross_profit_ttm"]
    rev = f["revenue_ttm"]
    if gm and gp and rev and rev > 0:
        computed_gm = gp / rev
        delta = abs(computed_gm - gm)
        if delta < 0.02:
            r.ok(ticker, "gross_margin_consistent", f"stored {gm:.3f} ≈ computed {computed_gm:.3f}")
        else:
            r.warn(ticker, "gross_margin_consistent",
                   f"stored {gm:.3f} vs gross_profit/revenue {computed_gm:.3f} ({delta:.3f} delta) — yfinance TTM mismatch is common")


def validate_prices(conn, ticker: str, r: Results, fail_fast: bool):
    rows = conn.execute("""
        SELECT date FROM prices WHERE ticker = ? ORDER BY date DESC LIMIT 10
    """, (ticker,)).fetchall()

    if not rows:
        r.fail(ticker, "prices_exist", "no price rows found")
        return

    latest = rows[0]["date"]
    today  = date.today()
    # Allow up to 4 calendar days lag (weekends + US holiday)
    lag = (today - date.fromisoformat(latest)).days
    if lag <= 4:
        r.ok(ticker, "prices_current", f"latest {latest} ({lag}d ago)")
    elif lag <= 10:
        r.warn(ticker, "prices_current", f"latest {latest} ({lag}d ago) — may need refresh")
    else:
        r.fail(ticker, "prices_current", f"latest {latest} ({lag}d ago) — stale")

    if fail_fast and r.failures: return

    # Check for gaps > 5 calendar days between consecutive dates
    all_dates = conn.execute("""
        SELECT date FROM prices WHERE ticker = ? ORDER BY date ASC
    """, (ticker,)).fetchall()

    max_gap = 0
    max_gap_pair = ("", "")
    for i in range(1, len(all_dates)):
        d1 = date.fromisoformat(all_dates[i-1]["date"])
        d2 = date.fromisoformat(all_dates[i]["date"])
        gap = (d2 - d1).days
        if gap > max_gap:
            max_gap = gap
            max_gap_pair = (all_dates[i-1]["date"], all_dates[i]["date"])

    if max_gap <= 5:
        r.ok(ticker, "prices_no_gaps", f"{len(all_dates)} rows, max gap {max_gap}d")
    elif max_gap <= 14:
        r.warn(ticker, "prices_no_gaps", f"gap of {max_gap}d between {max_gap_pair[0]} and {max_gap_pair[1]}")
    else:
        r.fail(ticker, "prices_no_gaps", f"large gap of {max_gap}d between {max_gap_pair[0]} and {max_gap_pair[1]}")


def validate_income(conn, ticker: str, r: Results):
    rows = conn.execute("""
        SELECT fiscal_year, revenue FROM income_annual
        WHERE ticker = ? AND revenue IS NOT NULL
        ORDER BY fiscal_year DESC
    """, (ticker,)).fetchall()

    if len(rows) >= 2:
        r.ok(ticker, "income_annual_depth", f"{len(rows)} fiscal years ({rows[-1]['fiscal_year'][:4]}–{rows[0]['fiscal_year'][:4]})")
    elif len(rows) == 1:
        r.warn(ticker, "income_annual_depth", "only 1 fiscal year — CAGR will be unavailable")
    else:
        r.warn(ticker, "income_annual_depth", "no income rows — growth scores will be 0")

    # Revenue should increase in at least one recent period (not a hard failure — cyclicals exist)
    if len(rows) >= 2 and rows[0]["revenue"] and rows[1]["revenue"]:
        if rows[0]["revenue"] >= rows[1]["revenue"]:
            r.ok(ticker, "revenue_not_declining", f"{rows[1]['fiscal_year'][:4]}→{rows[0]['fiscal_year'][:4]}: positive")
        else:
            r.warn(ticker, "revenue_not_declining",
                   f"revenue fell {rows[1]['fiscal_year'][:4]}→{rows[0]['fiscal_year'][:4]} — verify this is expected")


def validate_audit_log(conn, ticker: str, r: Results):
    latest = conn.execute("""
        SELECT fetched_at, endpoint, status, note FROM data_audit
        WHERE ticker = ? ORDER BY fetched_at DESC LIMIT 5
    """, (ticker,)).fetchall()

    if not latest:
        r.warn(ticker, "audit_log_exists", "no audit entries — run refresh.py to populate")
        return

    errors = [row for row in latest if row["status"] == "error"]
    if errors:
        r.warn(ticker, "audit_log_clean",
               f"{len(errors)} recent error(s) — last: {errors[0]['note'][:80]}")
    else:
        r.ok(ticker, "audit_log_clean", f"last fetch {latest[0]['fetched_at']} via {latest[0]['endpoint']}")


def validate_ticker(conn, ticker: str, r: Results, fail_fast: bool):
    validate_fundamentals(conn, ticker, r, fail_fast)
    if fail_fast and r.failures: return
    validate_prices(conn, ticker, r, fail_fast)
    if fail_fast and r.failures: return
    validate_income(conn, ticker, r)
    validate_audit_log(conn, ticker, r)


def print_results(r: Results, verbose: bool):
    if verbose:
        for ticker, status, check, detail in r.checks:
            line = f"  {status} [{ticker}] {check}"
            if detail:
                line += f"  —  {detail}"
            print(line)
    else:
        for ticker, status, check, detail in r.checks:
            if status != PASS:
                line = f"  {status} [{ticker}] {check}"
                if detail:
                    line += f"  —  {detail}"
                print(line)


def main():
    parser = argparse.ArgumentParser(description="Validate data integrity after refresh")
    parser.add_argument("tickers", nargs="*", help="Tickers to validate (default: all in screen_results)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure per ticker")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all checks, not just failures")
    args = parser.parse_args()

    init_db()
    conn = get_conn()

    tickers = [t.upper() for t in args.tickers]
    if not tickers:
        tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall()]

    if not tickers:
        print("No tickers found. Run refresh.py first.")
        sys.exit(1)

    print(f"\nPythia Data Validator — {date.today().isoformat()}")
    print(f"Checking {len(tickers)} ticker(s)...\n")

    r = Results()
    for ticker in tickers:
        validate_ticker(conn, ticker, r, args.fail_fast)

    conn.close()

    print_results(r, args.verbose)

    total  = len(r.checks)
    passed = len([c for c in r.checks if c[1] == PASS])
    warned = len(r.warnings)
    failed = len(r.failures)

    print(f"\n{'─'*50}")
    print(f"  {PASS} {passed} passed   {WARN} {warned} warnings   {FAIL} {failed} failed   ({total} checks)")

    if r.failures:
        print(f"\n  {failed} check(s) failed — review data above and re-run refresh.py if needed.")
        sys.exit(1)
    elif r.warnings:
        print(f"\n  All critical checks passed. {warned} warning(s) noted above.")
    else:
        print(f"\n  All checks passed.")


if __name__ == "__main__":
    main()
