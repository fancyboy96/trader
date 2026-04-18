# Trader — Long-Term Portfolio Plan

## Goal

Build a long-term equity portfolio by identifying high-promise stocks through fundamental analysis and news/sentiment trend monitoring.

---

## Research Process

For each candidate stock:

1. **News & Trend Screening** — identify themes with tailwinds (sectors, macro trends, policy shifts). Find companies well-positioned within them.
2. **Fundamental Analysis** — validate the business quality and valuation.
3. **Report** — produce a short HTML analysis report with a BUY / WATCH / PASS verdict.

---

## Fundamental Analysis Checklist

### Business Quality
- Revenue growth (3–5yr CAGR)
- Gross margin trend (expanding or stable?)
- Operating leverage (does profit grow faster than revenue?)
- Free cash flow generation and consistency
- Debt-to-equity, interest coverage
- Return on equity / return on invested capital

### Valuation
- P/E, forward P/E vs sector peers
- EV/EBITDA
- Price-to-FCF
- PEG ratio (P/E relative to growth rate)
- Discounted cash flow (simple 5yr projection)

### Competitive Position
- Moat: pricing power, switching costs, network effects, scale
- Market share trend
- Key risks to the business model

### Management
- Capital allocation track record (buybacks, dividends, acquisitions)
- Insider ownership and recent transactions
- Guidance history (do they beat or miss?)

---

## News & Trend Screening

Themes to monitor:
- AI infrastructure & compute
- Energy transition (grid, storage, nuclear)
- Defence & national security spending
- Healthcare / biotech breakthroughs
- Reshoring & supply chain localisation
- Consumer spending shifts

Sources:
- RSS / news API (e.g. NewsAPI, Polygon.io news feed)
- Earnings call transcripts (key language signals)
- SEC filings (10-K, 10-Q) — management discussion sections

---

## Data Layer

**SQLite + yfinance** (start here)
- Pull OHLCV, financials (income statement, balance sheet, cash flow), and key ratios
- Store in `data/trader.db` for offline querying and trend tracking
- Refresh with `scripts/refresh.py --tickers AAPL NVDA ...`

**News**
- NewsAPI (free tier: 100 req/day) or Polygon.io news endpoint
- Fetch recent headlines + summaries per ticker; store in `news` table
- Manual curation: flag articles as relevant/noise

---

## Report Structure

Each report is a self-contained HTML file in `planning/reports/TICKER-YYYY-MM-DD.html`.

Template: `planning/reports/_template.html`

### Sections
1. **Header** — ticker, company, date, price, sector
2. **Snapshot** — key stats grid (price, 52w range, market cap, revenue, P/E, FCF yield, debt/equity)
3. **Thesis** — 2–3 sentence investment case
4. **Fundamental Analysis** — revenue growth, margins, valuation vs peers
5. **News & Sentiment** — recent headlines, themes, any red flags
6. **Risks** — bear case, key threats
7. **Verdict** — BUY / WATCH / PASS with rationale and suggested position sizing

---

## Workflow

```
1. Identify a candidate (news trend, screener, tip)
2. python scripts/refresh.py --ticker NVDA        # load fundamentals into SQLite
3. python scripts/news.py --ticker NVDA           # fetch & store recent news
4. Write analysis manually in the HTML template   # or generate via script
5. Save report: planning/reports/NVDA-2026-04-18.html
6. Update watchlist.md with verdict + date
```

---

## File Layout

```
trader/
├── planning/
│   ├── plan.md                     ← this file
│   ├── watchlist.md                ← all candidates with verdict + date
│   └── reports/
│       ├── _template.html          ← shared HTML report template
│       └── TICKER-YYYY-MM-DD.html
├── data/
│   └── trader.db                   ← SQLite: financials, prices, news
└── scripts/
    ├── refresh.py                  ← pull fundamentals + OHLCV via yfinance
    └── news.py                     ← pull news headlines via NewsAPI / Polygon
```

---

## Open Questions

- [ ] Which news source? NewsAPI (easy) vs Polygon.io (richer, needs key) vs manual curation?
- [ ] Screener for initial candidates — use a tool (Finviz, Simplywall.st) or build filters in SQLite?
- [ ] DCF: simple manual inputs in the report, or scripted from loaded financials?
- [ ] Portfolio tracking — do we want a separate portfolio.md or dashboard once positions are taken?
