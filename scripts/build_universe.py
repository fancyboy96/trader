"""
Build and maintain the investment universe from ETF constituent lists.

Sources (in order):
  SPY  — S&P 500 via Wikipedia          (~503 tickers)
  QQQ  — NASDAQ-100 via Wikipedia       (~100 tickers, high overlap with SPY)
  XLV  — Health Care SPDR via SSGA xlsx
  XLI  — Industrials SPDR via SSGA xlsx
  SOXX — iShares Semiconductor via iShares CSV
  VGT  — Vanguard IT ETF via yfinance funds_data

If a provider source fails, it is skipped with a warning — the run continues.
Existing 'manual' tickers are never removed or deactivated.

Usage:
    python scripts/build_universe.py            # refresh all sources
    python scripts/build_universe.py --dry-run  # show counts without writing
"""

import argparse
import re
import time
from datetime import date
from io import BytesIO

import requests
import pandas as pd
import yfinance as yf

from db import get_conn, init_db

TODAY = date.today().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Ticker normalisation ─────────────────────────────────────────────────────

def normalise(ticker: str) -> str | None:
    """Convert provider ticker format to yfinance-compatible. Return None to skip."""
    t = str(ticker).strip().upper()
    if not t or t in ("NAN", "-", "N/A", "CASH", "OTHER"):
        return None
    t = t.replace(".", "-")       # BRK.B → BRK-B
    if re.search(r"[^A-Z0-9\-]", t):
        return None               # skip anything with spaces, slashes, etc.
    return t


# ── Source fetchers ──────────────────────────────────────────────────────────

def _wikipedia_tables(url: str) -> list:
    """Fetch a Wikipedia page via requests (avoids 403) and parse with pandas."""
    from io import StringIO
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return pd.read_html(StringIO(r.text))


def fetch_wikipedia_sp500() -> list[dict]:
    """S&P 500 constituents from Wikipedia. Very reliable — well-maintained table."""
    tables = _wikipedia_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = tables[0]
    tickers = []
    for raw in df["Symbol"].tolist():
        t = normalise(raw)
        if t:
            tickers.append({"ticker": t, "source": "SPY", "weight": None})
    return tickers


def fetch_wikipedia_nasdaq100() -> list[dict]:
    """NASDAQ-100 constituents from Wikipedia."""
    tables = _wikipedia_tables("https://en.wikipedia.org/wiki/Nasdaq-100")
    for tbl in tables:
        cols = [str(c).strip() for c in tbl.columns]
        ticker_col = next((c for c in cols if "ticker" in c.lower() or "symbol" in c.lower()), None)
        if ticker_col and len(tbl) > 50:
            tickers = []
            for raw in tbl[ticker_col].tolist():
                t = normalise(raw)
                if t:
                    tickers.append({"ticker": t, "source": "QQQ", "weight": None})
            return tickers
    raise ValueError("NASDAQ-100 table not found on Wikipedia page")


def fetch_ssga_xlsx(etf: str) -> list[dict]:
    """SSGA/SPDR ETF holdings from their daily xlsx download."""
    url = (
        "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/"
        f"fund-data/etfs/us/holdings-daily-us-en-{etf.lower()}.xlsx"
    )
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    # SSGA xlsx: first few rows are metadata; actual column headers are on row ~4
    raw = pd.read_excel(BytesIO(r.content), header=None)
    # find the header row (contains 'Ticker' or 'Name' and 'Weight')
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(v).strip().lower() for v in row.values]
        if any("ticker" in v or "identifier" in v for v in vals):
            header_row = i
            break
    if header_row is None:
        raise ValueError(f"Could not locate header row in {etf} xlsx")
    df = pd.read_excel(BytesIO(r.content), skiprows=header_row + 1, header=0)
    # re-read with the correct header
    raw2 = pd.read_excel(BytesIO(r.content), header=header_row)
    df = raw2
    cols_lower = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    ticker_col = next(
        (cols_lower[k] for k in cols_lower if "ticker" in k or "identifier" in k), None
    )
    weight_col = next(
        (cols_lower[k] for k in cols_lower if "weight" in k), None
    )
    if not ticker_col:
        raise ValueError(f"No ticker column found in {etf} xlsx. Columns: {list(df.columns)}")
    rows = []
    for _, row in df.iterrows():
        t = normalise(row[ticker_col])
        if not t:
            continue
        w = None
        if weight_col:
            try:
                w = float(row[weight_col]) / 100  # SSGA stores as percentage
            except (ValueError, TypeError):
                pass
        rows.append({"ticker": t, "source": etf, "weight": w})
    return rows


def fetch_ishares_csv(etf: str, product_id: str, fund_slug: str) -> list[dict]:
    """iShares (BlackRock) ETF holdings via their CSV export endpoint."""
    url = (
        f"https://www.ishares.com/us/products/{product_id}/{fund_slug}/"
        f"1467271812596.ajax?fileType=csv&fileName={etf}_holdings&dataType=fund"
    )
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    text = r.text
    # iShares CSV has several header/metadata lines before the actual data
    lines = text.splitlines()
    data_start = None
    for i, line in enumerate(lines):
        if "Ticker" in line or "ISIN" in line:
            data_start = i
            break
    if data_start is None:
        raise ValueError(f"Could not find header row in {etf} iShares CSV")
    from io import StringIO
    df = pd.read_csv(StringIO("\n".join(lines[data_start:])))
    cols_lower = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    ticker_col = next(
        (cols_lower[k] for k in cols_lower if k == "ticker"), None
    )
    weight_col = next(
        (cols_lower[k] for k in cols_lower if "weight" in k), None
    )
    if not ticker_col:
        raise ValueError(f"No 'Ticker' column in {etf} CSV. Columns: {list(df.columns)}")
    rows = []
    for _, row in df.iterrows():
        t = normalise(row[ticker_col])
        if not t:
            continue
        w = None
        if weight_col:
            try:
                w = float(str(row[weight_col]).replace("%", "").strip()) / 100
            except (ValueError, TypeError):
                pass
        rows.append({"ticker": t, "source": etf, "weight": w})
    return rows


def fetch_yfinance_etf(etf: str) -> list[dict]:
    """ETF top holdings via yfinance funds_data (limited to top ~25)."""
    t = yf.Ticker(etf)
    try:
        holdings = t.funds_data.top_holdings
        if holdings is None or holdings.empty:
            raise ValueError("empty")
        rows = []
        for ticker_raw in holdings.index:
            t_norm = normalise(ticker_raw)
            if t_norm:
                rows.append({"ticker": t_norm, "source": etf, "weight": None})
        return rows
    except Exception as e:
        raise ValueError(f"yfinance funds_data failed for {etf}: {e}")


# ── Source registry ──────────────────────────────────────────────────────────

SOURCES = [
    {"id": "SPY",  "label": "S&P 500 (Wikipedia)",              "fn": fetch_wikipedia_sp500},
    {"id": "QQQ",  "label": "NASDAQ-100 (Wikipedia)",            "fn": fetch_wikipedia_nasdaq100},
    {"id": "XLV",  "label": "Health Care SPDR (yfinance top-25)","fn": lambda: fetch_yfinance_etf("XLV")},
    {"id": "XLI",  "label": "Industrials SPDR (yfinance top-25)","fn": lambda: fetch_yfinance_etf("XLI")},
    {"id": "SOXX", "label": "Semiconductors (iShares CSV)",
     "fn": lambda: fetch_ishares_csv("SOXX", "239705", "ISHARES-SEMICONDUCTOR-ETF")},
    {"id": "VGT",  "label": "Vanguard IT ETF (yfinance top-25)", "fn": lambda: fetch_yfinance_etf("VGT")},
]


# ── DB write ─────────────────────────────────────────────────────────────────

def upsert_universe(conn, ticker: str, source: str, weight: float | None):
    """Insert or merge a ticker into the universe table."""
    existing = conn.execute(
        "SELECT source, weight FROM universe WHERE ticker=?", (ticker,)
    ).fetchone()

    if existing:
        # Merge sources (union, deduplicated)
        sources = set(existing["source"].split(",")) | {source}
        # Keep the higher weight
        w = existing["weight"]
        if weight is not None and (w is None or weight > w):
            w = weight
        conn.execute(
            "UPDATE universe SET source=?, weight=?, active=1 WHERE ticker=?",
            (",".join(sorted(sources)), w, ticker),
        )
    else:
        conn.execute(
            "INSERT INTO universe (ticker, source, weight, added_date, active) VALUES (?,?,?,?,1)",
            (ticker, source, weight, TODAY),
        )


def migrate_manual_tickers(conn):
    """Ensure all tickers already in companies are present in universe as 'manual'."""
    tickers = [r[0] for r in conn.execute(
        "SELECT ticker FROM companies WHERE ticker NOT IN (SELECT ticker FROM universe)"
    ).fetchall()]
    for t in tickers:
        conn.execute(
            "INSERT OR IGNORE INTO universe (ticker, source, weight, added_date, active) VALUES (?,?,?,?,1)",
            (t, "manual", None, TODAY),
        )
    return len(tickers)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build Pythia investment universe from ETF holdings")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count without writing to DB")
    args = parser.parse_args()

    init_db()
    conn = get_conn()

    # Migrate existing manual tickers first
    migrated = migrate_manual_tickers(conn)
    if migrated:
        print(f"  Migrated {migrated} manual ticker(s) → universe table")
        conn.commit()

    total_added = 0
    all_new = {}  # ticker → {source, weight}

    for src in SOURCES:
        print(f"  [{src['id']}] {src['label']} ...", end=" ", flush=True)
        try:
            rows = src["fn"]()
            for r in rows:
                t = r["ticker"]
                if t not in all_new:
                    all_new[t] = {"source": r["source"], "weight": r["weight"]}
                else:
                    # merge source
                    existing_sources = set(all_new[t]["source"].split(",")) | {r["source"]}
                    all_new[t]["source"] = ",".join(sorted(existing_sources))
                    if r["weight"] is not None:
                        if all_new[t]["weight"] is None or r["weight"] > all_new[t]["weight"]:
                            all_new[t]["weight"] = r["weight"]
            print(f"{len(rows)} holdings")
        except Exception as e:
            print(f"FAILED — {e}")
        time.sleep(0.5)

    if args.dry_run:
        print(f"\nDry run — {len(all_new)} unique tickers across all sources (nothing written)")
        conn.close()
        return

    before = conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
    for ticker, data in all_new.items():
        upsert_universe(conn, ticker, data["source"], data["weight"])
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]

    print(f"\n  Universe: {before} → {after} tickers (+{after - before} new)")
    conn.close()


if __name__ == "__main__":
    main()
