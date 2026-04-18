"""
Pull fundamentals and price history for one or more tickers via yfinance.
Upserts into trader.db.

Usage:
    python scripts/refresh.py NVDA AAPL MSFT
    python scripts/refresh.py --all          (refreshes every ticker in companies table)
"""

import sys
import argparse
from datetime import date, datetime
import yfinance as yf
from db import get_conn, init_db


def log_audit(conn, ticker: str, endpoint: str, rows: int, status: str, note: str = ""):
    conn.execute(
        "INSERT INTO data_audit (ticker, fetched_at, endpoint, rows_returned, status, note) VALUES (?,?,?,?,?,?)",
        (ticker, datetime.utcnow().isoformat(timespec="seconds") + "Z", endpoint, rows, status, note),
    )


def upsert_company(conn, ticker: str, info: dict):
    conn.execute("""
        INSERT INTO companies (ticker, name, sector, industry, country, description, website, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            name=excluded.name, sector=excluded.sector, industry=excluded.industry,
            country=excluded.country, description=excluded.description,
            website=excluded.website, last_updated=excluded.last_updated
    """, (
        ticker,
        info.get("longName") or info.get("shortName"),
        info.get("sector"),
        info.get("industry"),
        info.get("country"),
        info.get("longBusinessSummary"),
        info.get("website"),
        date.today().isoformat(),
    ))


def upsert_fundamentals(conn, ticker: str, info: dict):
    snapshot = date.today().isoformat()

    # Derive price-to-FCF safely
    mcap = info.get("marketCap")
    fcf  = info.get("freeCashflow")
    p_fcf = round(mcap / fcf, 2) if mcap and fcf and fcf > 0 else None

    conn.execute("""
        INSERT INTO fundamentals (
            ticker, snapshot_date, market_cap, enterprise_value,
            revenue_ttm, gross_profit_ttm, operating_income_ttm, net_income_ttm,
            ebitda, free_cashflow, total_debt, total_equity,
            eps_ttm, pe_ratio, fwd_pe, ev_ebitda, price_to_fcf, peg_ratio,
            roe, gross_margin, net_margin, operating_margin,
            debt_to_equity, current_ratio, beta, dividend_yield
        ) VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        ON CONFLICT(ticker, snapshot_date) DO UPDATE SET
            market_cap=excluded.market_cap,
            enterprise_value=excluded.enterprise_value,
            revenue_ttm=excluded.revenue_ttm,
            gross_profit_ttm=excluded.gross_profit_ttm,
            operating_income_ttm=excluded.operating_income_ttm,
            net_income_ttm=excluded.net_income_ttm,
            ebitda=excluded.ebitda,
            free_cashflow=excluded.free_cashflow,
            total_debt=excluded.total_debt,
            total_equity=excluded.total_equity,
            eps_ttm=excluded.eps_ttm,
            pe_ratio=excluded.pe_ratio,
            fwd_pe=excluded.fwd_pe,
            ev_ebitda=excluded.ev_ebitda,
            price_to_fcf=excluded.price_to_fcf,
            peg_ratio=excluded.peg_ratio,
            roe=excluded.roe,
            gross_margin=excluded.gross_margin,
            net_margin=excluded.net_margin,
            operating_margin=excluded.operating_margin,
            debt_to_equity=excluded.debt_to_equity,
            current_ratio=excluded.current_ratio,
            beta=excluded.beta,
            dividend_yield=excluded.dividend_yield
    """, (
        ticker, snapshot,
        info.get("marketCap"),
        info.get("enterpriseValue"),
        info.get("totalRevenue"),
        info.get("grossProfits"),
        info.get("operatingCashflow"),  # yfinance doesn't expose op income directly in info
        info.get("netIncomeToCommon"),
        info.get("ebitda"),
        fcf,
        info.get("totalDebt"),
        info.get("totalStockholderEquity") or info.get("bookValue"),
        info.get("trailingEps"),
        info.get("trailingPE"),
        info.get("forwardPE"),
        info.get("enterpriseToEbitda"),
        p_fcf,
        info.get("pegRatio"),
        info.get("returnOnEquity"),
        info.get("grossMargins"),
        info.get("profitMargins"),
        info.get("operatingMargins"),
        (info["debtToEquity"] / 100) if info.get("debtToEquity") is not None else None,
        info.get("currentRatio"),
        info.get("beta"),
        info.get("dividendYield"),
    ))


def upsert_prices(conn, ticker: str, hist):
    rows = []
    for dt, row in hist.iterrows():
        rows.append((
            ticker,
            dt.date().isoformat(),
            round(float(row["Open"]), 4),
            round(float(row["High"]), 4),
            round(float(row["Low"]), 4),
            round(float(row["Close"]), 4),
            int(row["Volume"]),
        ))
    conn.executemany("""
        INSERT INTO prices (ticker, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume
    """, rows)
    return len(rows)


def upsert_income_annual(conn, ticker: str, financials):
    """Store annual income statement rows (yfinance returns columns as fiscal year dates)."""
    rows = []
    for col in financials.columns:
        fy = col.date().isoformat() if hasattr(col, "date") else str(col)[:10]
        def g(key):
            val = financials.loc[key, col] if key in financials.index else None
            return float(val) if val is not None and str(val) != "nan" else None
        rows.append((
            ticker, fy,
            g("Total Revenue"),
            g("Gross Profit"),
            g("Operating Income"),
            g("Net Income"),
            g("EBITDA"),
            g("Basic EPS"),
        ))
    conn.executemany("""
        INSERT INTO income_annual (ticker, fiscal_year, revenue, gross_profit, operating_income, net_income, ebitda, eps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, fiscal_year) DO UPDATE SET
            revenue=excluded.revenue, gross_profit=excluded.gross_profit,
            operating_income=excluded.operating_income, net_income=excluded.net_income,
            ebitda=excluded.ebitda, eps=excluded.eps
    """, rows)
    return len(rows)


def refresh_ticker(ticker: str):
    ticker = ticker.upper()
    print(f"  [{ticker}] fetching ...", end=" ", flush=True)

    t = yf.Ticker(ticker)
    info = t.info

    if not info or info.get("quoteType") == "NONE":
        print("not found — skipped")
        conn = get_conn()
        log_audit(conn, ticker, "info", 0, "empty", "quoteType=NONE or no info returned")
        conn.commit()
        conn.close()
        return

    conn = get_conn()
    try:
        upsert_company(conn, ticker, info)
        upsert_fundamentals(conn, ticker, info)
        log_audit(conn, ticker, "info", 1, "ok")

        hist = t.history(period="2y")
        if not hist.empty:
            price_rows = upsert_prices(conn, ticker, hist)
            log_audit(conn, ticker, "history", price_rows, "ok")
        else:
            price_rows = 0
            log_audit(conn, ticker, "history", 0, "empty")

        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                inc_rows = upsert_income_annual(conn, ticker, fin)
                log_audit(conn, ticker, "financials", inc_rows, "ok")
            else:
                inc_rows = 0
                log_audit(conn, ticker, "financials", 0, "empty")
        except Exception as e:
            inc_rows = 0
            log_audit(conn, ticker, "financials", 0, "error", str(e))

        conn.commit()
        name = info.get("longName") or info.get("shortName") or ticker
        print(f"ok — {name} | {price_rows} price rows | {inc_rows} income rows")
    except Exception as e:
        conn.rollback()
        log_audit(conn, ticker, "info", 0, "error", str(e))
        conn.commit()
        print(f"error — {e}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Refresh fundamentals and prices for tickers")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols")
    parser.add_argument("--all", action="store_true", help="Refresh all tickers in companies table")
    args = parser.parse_args()

    init_db()

    tickers = args.tickers
    if args.all:
        conn = get_conn()
        tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM companies").fetchall()]
        conn.close()

    if not tickers:
        parser.print_help()
        sys.exit(1)

    print(f"Refreshing {len(tickers)} ticker(s)...")
    for t in tickers:
        refresh_ticker(t)
    print("Done.")


if __name__ == "__main__":
    main()
