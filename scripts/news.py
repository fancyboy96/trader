"""
Fetch recent news for tickers via yfinance and store in trader.db.
yfinance pulls from Yahoo Finance news — no API key required.

Usage:
    python scripts/news.py NVDA AAPL
    python scripts/news.py --all
"""

import sys
import argparse
import hashlib
from datetime import datetime, timezone
import yfinance as yf
from db import get_conn, init_db


def _make_id(ticker: str, url: str) -> str:
    return hashlib.sha1(f"{ticker}:{url}".encode()).hexdigest()[:16]


def _ts(unix: int | None) -> str | None:
    if not unix:
        return None
    return datetime.fromtimestamp(unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def fetch_news(ticker: str):
    ticker = ticker.upper()
    print(f"  [{ticker}] fetching news ...", end=" ", flush=True)

    t = yf.Ticker(ticker)
    try:
        items = t.news or []
    except Exception as e:
        print(f"error — {e}")
        return

    if not items:
        print("no news returned")
        return

    conn = get_conn()
    inserted = 0
    skipped = 0
    for item in items:
        # yfinance >=0.2.40 wraps everything under item['content']
        c = item.get("content") or item
        url   = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url") or c.get("link") or ""
        title = c.get("title") or ""
        provider = c.get("provider") or {}
        source = provider.get("displayName") or provider.get("name") or c.get("publisher") or ""
        summary = c.get("summary") or c.get("description") or ""
        pub = c.get("pubDate") or c.get("publishedAt")
        # pubDate is ISO string "2026-04-17T21:55:15Z"; providerPublishTime is unix int
        if isinstance(pub, int):
            published = _ts(pub)
        elif isinstance(pub, str):
            published = pub.replace("T", " ").replace("Z", "")
        else:
            published = None

        if not title or not url:
            skipped += 1
            continue

        news_id = _make_id(ticker, url)
        try:
            conn.execute("""
                INSERT INTO news (id, ticker, published_at, title, summary, source, url, sentiment)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(id) DO NOTHING
            """, (news_id, ticker, published, title, summary, source, url))
            inserted += conn.execute("SELECT changes()").fetchone()[0]
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()
    print(f"{inserted} new | {len(items) - inserted - skipped} already stored | {skipped} skipped")


def print_news(ticker: str, limit: int = 10):
    """Print stored news for a ticker to stdout."""
    ticker = ticker.upper()
    conn = get_conn()
    rows = conn.execute("""
        SELECT published_at, source, title, url
        FROM news
        WHERE ticker = ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (ticker, limit)).fetchall()
    conn.close()

    if not rows:
        print(f"No news stored for {ticker}. Run: python scripts/news.py {ticker}")
        return

    print(f"\n{ticker} — {len(rows)} most recent articles\n")
    for r in rows:
        print(f"  {r['published_at'][:10]}  [{r['source']}]  {r['title']}")
        print(f"           {r['url']}\n")


def main():
    parser = argparse.ArgumentParser(description="Fetch news for tickers via yfinance")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols")
    parser.add_argument("--all", action="store_true", help="Fetch news for all tickers in companies table")
    parser.add_argument("--show", metavar="TICKER", help="Print stored news for a ticker")
    args = parser.parse_args()

    init_db()

    if args.show:
        print_news(args.show)
        return

    tickers = args.tickers
    if args.all:
        conn = get_conn()
        tickers = [r["ticker"] for r in conn.execute("SELECT ticker FROM companies").fetchall()]
        conn.close()

    if not tickers:
        parser.print_help()
        sys.exit(1)

    print(f"Fetching news for {len(tickers)} ticker(s)...")
    for t in tickers:
        fetch_news(t)
    print("Done.")


if __name__ == "__main__":
    main()
