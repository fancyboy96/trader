"""
Screens all tickers in the database against criteria defined in
planning/screening-criteria.md. Writes results to screen_results table.

Usage:
    python scripts/screen.py
    python scripts/screen.py --min-tier B    # only show B or better
    python scripts/screen.py --verbose       # show score breakdown
"""

import argparse
from datetime import date
from db import get_conn, init_db


# ── Pass/fail thresholds ────────────────────────────────────────────────────

FILTERS = {
    "market_cap":    (">=", 2_000_000_000),
    "revenue_ttm":   (">=",   500_000_000),
    "gross_margin":  (">=",          0.30),
    "debt_to_equity":("<=",          2.0),
    "current_ratio": (">=",          1.0),
    "free_cashflow": (">",              0),
}


def apply_filters(f) -> tuple[bool, str | None]:
    for col, (op, threshold) in FILTERS.items():
        val = f[col]
        if val is None:
            return False, f"{col} missing"
        if op == ">="  and not (val >= threshold): return False, f"{col} {val:.2g} < {threshold:.2g}"
        if op == "<="  and not (val <= threshold): return False, f"{col} {val:.2g} > {threshold:.2g}"
        if op == ">"   and not (val >  threshold): return False, f"{col} {val:.2g} <= {threshold:.2g}"
    return True, None


# ── Scoring helpers ─────────────────────────────────────────────────────────

def band(val, low, mid, pts_low, pts_mid, pts_high, reverse=False):
    """Return pts based on which band val falls in. None → 0."""
    if val is None:
        return 0
    if reverse:
        if val > low:   return 0
        if val > mid:   return pts_mid
        return pts_high
    else:
        if val < low:   return 0
        if val < mid:   return pts_low
        return pts_high


def score_growth(f, revenue_growth_yoy, revenue_cagr_3y, eps_growth_yoy) -> float:
    s  = band(revenue_growth_yoy, 0.05, 0.15,  5, 5, 10)
    s += band(revenue_cagr_3y,    0.05, 0.20,  5, 5, 10)
    s += band(eps_growth_yoy,     0.00, 0.15,  5, 5, 10)
    return float(s)


def score_profitability(f) -> float:
    s  = band(f["gross_margin"],  0.30, 0.50,  5, 5, 10)
    s += band(f["net_margin"],    0.05, 0.15,  5, 5, 10)
    s += band(f["roe"],           0.10, 0.20,  3, 3,  5)
    return float(s)


def score_valuation(f) -> float:
    # Lower fwd_pe is better → reverse
    s  = band(f["fwd_pe"],    50, 25, 0, 5, 10, reverse=True)
    s += band(f["peg_ratio"],  3, 1.5, 0, 5, 10, reverse=True)
    # FCF yield: fcf / market_cap
    fcf_yield = None
    if f["free_cashflow"] and f["market_cap"] and f["market_cap"] > 0:
        fcf_yield = f["free_cashflow"] / f["market_cap"]
    s += band(fcf_yield, 0.01, 0.03, 3, 3, 5)
    return float(s)


def score_balance_sheet(f) -> float:
    s  = band(f["debt_to_equity"], 0.5, 1.5, 10, 5, 0, reverse=True)
    s += band(f["current_ratio"],  1.2, 2.0,  3, 3, 5)
    s += 5 if (f["free_cashflow"] or 0) > 0 else 0
    return float(s)


def tier_from_score(score: float) -> str:
    if score >= 75: return "A"
    if score >= 50: return "B"
    if score >= 25: return "C"
    return "D"


# ── Revenue growth helpers ──────────────────────────────────────────────────

def compute_growth(conn, ticker: str) -> tuple[float | None, float | None, float | None]:
    rows = conn.execute("""
        SELECT fiscal_year, revenue, eps FROM income_annual
        WHERE ticker = ? AND revenue IS NOT NULL
        ORDER BY fiscal_year DESC
        LIMIT 4
    """, (ticker,)).fetchall()

    revenue_growth_yoy = None
    revenue_cagr_3y    = None
    eps_growth_yoy     = None

    if len(rows) >= 2:
        r0, r1 = rows[0]["revenue"], rows[1]["revenue"]
        if r1 and r1 > 0:
            revenue_growth_yoy = (r0 - r1) / r1

        e0 = rows[0]["eps"]
        e1 = rows[1]["eps"]
        if e0 is not None and e1 and e1 > 0:
            eps_growth_yoy = (e0 - e1) / e1

    if len(rows) >= 4:
        r0, r3 = rows[0]["revenue"], rows[3]["revenue"]
        if r3 and r3 > 0:
            revenue_cagr_3y = (r0 / r3) ** (1 / 3) - 1

    return revenue_growth_yoy, revenue_cagr_3y, eps_growth_yoy


# ── Momentum ────────────────────────────────────────────────────────────────

def compute_momentum(conn, ticker: str) -> tuple[float | None, float | None]:
    """Return (momentum_90d, relative_momentum_vs_spy). Both None if data unavailable."""
    def price_return_90d(t: str) -> float | None:
        latest = conn.execute(
            "SELECT close, date FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1", (t,)
        ).fetchone()
        if not latest:
            return None
        past = conn.execute(
            "SELECT close FROM prices WHERE ticker=? AND date <= date(?, '-90 days') ORDER BY date DESC LIMIT 1",
            (t, latest["date"])
        ).fetchone()
        if not past or not past["close"] or past["close"] == 0:
            return None
        return (latest["close"] / past["close"]) - 1

    ticker_mom = price_return_90d(ticker)
    spy_mom    = price_return_90d("SPY")
    if ticker_mom is None:
        return None, None
    rel = (ticker_mom - spy_mom) if spy_mom is not None else None
    return ticker_mom, rel


# ── Main ────────────────────────────────────────────────────────────────────

def run_screen(min_tier: str = "D", verbose: bool = False):
    init_db()
    conn = get_conn()

    # Latest fundamentals snapshot per ticker
    rows = conn.execute("""
        SELECT f.*, c.name, c.sector, c.industry
        FROM fundamentals f
        JOIN (
            SELECT ticker, MAX(snapshot_date) as latest
            FROM fundamentals GROUP BY ticker
        ) latest ON f.ticker = latest.ticker AND f.snapshot_date = latest.latest
        LEFT JOIN companies c ON f.ticker = c.ticker
        ORDER BY f.ticker
    """).fetchall()

    run_date = date.today().isoformat()
    results  = []

    for f in rows:
        ticker = f["ticker"]
        passed, fail_reason = apply_filters(f)

        rev_yoy, rev_cagr, eps_yoy = compute_growth(conn, ticker)
        mom_90d, rel_mom = compute_momentum(conn, ticker)

        if passed:
            sg  = score_growth(f, rev_yoy, rev_cagr, eps_yoy)
            sp  = score_profitability(f)
            sv  = score_valuation(f)
            sb  = score_balance_sheet(f)
            total = sg + sp + sv + sb
            t   = tier_from_score(total)
        else:
            sg = sp = sv = sb = total = 0.0
            t = "D"

        conn.execute("""
            INSERT INTO screen_results (
                ticker, run_date, passed_filters, filter_fail_reason,
                score, tier, score_growth, score_profitability, score_valuation, score_balance_sheet,
                revenue_growth_yoy, revenue_cagr_3y, eps_growth_yoy,
                momentum_90d, relative_momentum
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                run_date=excluded.run_date, passed_filters=excluded.passed_filters,
                filter_fail_reason=excluded.filter_fail_reason, score=excluded.score,
                tier=excluded.tier, score_growth=excluded.score_growth,
                score_profitability=excluded.score_profitability, score_valuation=excluded.score_valuation,
                score_balance_sheet=excluded.score_balance_sheet,
                revenue_growth_yoy=excluded.revenue_growth_yoy,
                revenue_cagr_3y=excluded.revenue_cagr_3y,
                eps_growth_yoy=excluded.eps_growth_yoy,
                momentum_90d=excluded.momentum_90d,
                relative_momentum=excluded.relative_momentum
        """, (ticker, run_date, int(passed), fail_reason,
              total, t, sg, sp, sv, sb, rev_yoy, rev_cagr, eps_yoy,
              mom_90d, rel_mom))

        results.append({
            "ticker": ticker, "name": f["name"], "sector": f["sector"],
            "passed": passed, "fail_reason": fail_reason,
            "score": total, "tier": t,
            "sg": sg, "sp": sp, "sv": sv, "sb": sb,
            "rev_yoy": rev_yoy, "rev_cagr": rev_cagr, "eps_yoy": eps_yoy,
            "momentum_90d": mom_90d, "relative_momentum": rel_mom,
        })

    conn.commit()
    conn.close()

    # Filter and sort for display
    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    min_order  = tier_order.get(min_tier, 3)
    display    = [r for r in results if tier_order[r["tier"]] <= min_order and r["passed"]]
    display.sort(key=lambda r: -r["score"])

    # Print results
    tier_counts = {t: sum(1 for r in results if r["tier"] == t and r["passed"]) for t in "ABCD"}
    filtered    = sum(1 for r in results if not r["passed"])

    print(f"\nPythia Screener — {run_date}")
    print(f"Tickers: {len(results)} | Passed: {len(results)-filtered} | "
          f"A:{tier_counts['A']}  B:{tier_counts['B']}  C:{tier_counts['C']}  D:{tier_counts['D']} | "
          f"Filtered (fail): {filtered}\n")

    if not display:
        print(f"  No tickers at tier {min_tier} or better.")
        return

    col = "{:<6} {:<4} {:>6} {:>8} {:>8}"
    print(col.format("TICKER", "TIER", "SCORE", "SECTOR", "NAME"))
    print("─" * 70)
    for r in display:
        sector = (r["sector"] or "")[:20]
        name   = (r["name"] or "")[:28]
        print(col.format(r["ticker"], r["tier"], f"{r['score']:.0f}", sector, name))
        if verbose:
            def pct(v): return f"{v*100:.1f}%" if v is not None else "n/a"
            print(f"         Growth:{r['sg']:.0f}  Profit:{r['sp']:.0f}  Val:{r['sv']:.0f}  BS:{r['sb']:.0f}"
                  f"  RevYoY:{pct(r['rev_yoy'])}  CAGR3y:{pct(r['rev_cagr'])}  EPSg:{pct(r['eps_yoy'])}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Run Pythia fundamental screener")
    parser.add_argument("--min-tier", default="B", choices=["A","B","C","D"],
                        help="Minimum tier to display (default: B)")
    parser.add_argument("--verbose", action="store_true", help="Show score breakdown per ticker")
    args = parser.parse_args()
    run_screen(args.min_tier, args.verbose)


if __name__ == "__main__":
    main()
