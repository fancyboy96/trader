"""
Database schema and connection helpers.
All scripts import get_conn() from here.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "trader.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            ticker          TEXT PRIMARY KEY,
            name            TEXT,
            exchange        TEXT,
            sector          TEXT,
            industry        TEXT,
            country         TEXT,
            description     TEXT,
            website         TEXT,
            last_updated    TEXT
        );

        -- One row per ticker per snapshot date (re-running refresh upserts)
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker              TEXT,
            snapshot_date       TEXT,
            market_cap          REAL,
            enterprise_value    REAL,
            revenue_ttm         REAL,
            gross_profit_ttm    REAL,
            operating_income_ttm REAL,
            net_income_ttm      REAL,
            ebitda              REAL,
            free_cashflow       REAL,
            total_debt          REAL,
            total_equity        REAL,
            eps_ttm             REAL,
            pe_ratio            REAL,
            fwd_pe              REAL,
            ev_ebitda           REAL,
            price_to_fcf        REAL,
            peg_ratio           REAL,
            roe                 REAL,
            gross_margin        REAL,
            net_margin          REAL,
            operating_margin    REAL,
            debt_to_equity      REAL,
            current_ratio       REAL,
            beta                REAL,
            dividend_yield      REAL,
            PRIMARY KEY (ticker, snapshot_date)
        );

        -- Daily OHLCV — yfinance history
        CREATE TABLE IF NOT EXISTS prices (
            ticker  TEXT,
            date    TEXT,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            PRIMARY KEY (ticker, date)
        );

        -- Annual income statement rows (one row per ticker per year)
        CREATE TABLE IF NOT EXISTS income_annual (
            ticker              TEXT,
            fiscal_year         TEXT,
            revenue             REAL,
            gross_profit        REAL,
            operating_income    REAL,
            net_income          REAL,
            ebitda              REAL,
            eps                 REAL,
            PRIMARY KEY (ticker, fiscal_year)
        );

        -- News items fetched via yfinance; sentiment filled manually or later via NLP
        CREATE TABLE IF NOT EXISTS news (
            id              TEXT PRIMARY KEY,
            ticker          TEXT,
            published_at    TEXT,
            title           TEXT,
            summary         TEXT,
            source          TEXT,
            url             TEXT,
            sentiment       TEXT    -- NULL | positive | negative | neutral
        );

        -- Latest screener output — one row per ticker, overwritten each run
        CREATE TABLE IF NOT EXISTS screen_results (
            ticker              TEXT PRIMARY KEY,
            run_date            TEXT,
            passed_filters      INTEGER,  -- 0 | 1
            filter_fail_reason  TEXT,
            score               REAL,
            tier                TEXT,     -- A | B | C | D
            score_growth        REAL,
            score_profitability REAL,
            score_valuation     REAL,
            score_balance_sheet REAL,
            revenue_growth_yoy  REAL,
            revenue_cagr_3y     REAL,
            eps_growth_yoy      REAL
        );

        -- Audit log for every API fetch attempt
        CREATE TABLE IF NOT EXISTS data_audit (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT,
            fetched_at      TEXT,
            endpoint        TEXT,   -- info | history | financials | news
            rows_returned   INTEGER,
            status          TEXT,   -- ok | error | empty
            note            TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker ON fundamentals(ticker);
        CREATE INDEX IF NOT EXISTS idx_prices_ticker       ON prices(ticker);
        CREATE INDEX IF NOT EXISTS idx_news_ticker         ON news(ticker);
        CREATE INDEX IF NOT EXISTS idx_news_published      ON news(published_at);
        CREATE INDEX IF NOT EXISTS idx_audit_ticker        ON data_audit(ticker);
        CREATE INDEX IF NOT EXISTS idx_audit_fetched       ON data_audit(fetched_at);
    """)
    conn.commit()
    conn.close()
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    init_db()
