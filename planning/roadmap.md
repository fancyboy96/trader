# Pythia — Product Roadmap

A phased plan for evolving Pythia from a manual research tool into a systematic, data-driven research platform. Each phase builds on the last. Nothing in a later phase is attempted before the prior phase is stable.

---

## Principles

**Data quality before data quantity.** A 41-ticker universe with verified, consistent data is more valuable than a 500-ticker universe with silent errors. Every expansion of scope follows a validation step.

**Discovery before depth.** The biggest gap right now is that we only see stocks we already know about. Closing that gap — surfacing candidates we haven't thought of — has higher value than adding more analysis depth to stocks already in the system.

**Systematic before manual.** Any step in the research process that is repeated identically each time is a candidate for automation. Human judgment is reserved for steps that genuinely require it: writing a thesis, sizing a position, making a decision.

**Verdict integrity.** A BUY verdict in a report is a serious claim. The roadmap does not chase features that make it easier to generate verdicts — it builds the infrastructure that makes verdicts more trustworthy.

---

## Current State (Phase 0 — Complete)

Pythia is a functional research tool. The foundation is solid.

**What works:**
- SQLite database with fundamentals, prices, annual income, news, audit log
- yfinance pipeline: refresh, news, validation
- Screener: hard filters + 100pt scoring across Growth / Profitability / Valuation / Balance Sheet
- Static site: landing, dashboard (with grouping), plays, company profiles, full analysis reports
- 41 tickers, 4 plays, 8 Tier A reports
- Data provenance: audit log, fetch timestamps on every page, validate.py with sanity checks

**What it cannot do yet:**
- Surface stocks it has never seen
- Detect emerging themes automatically
- Compare a stock against its sector peers
- Track positions or portfolio-level performance
- Alert when something material changes

---

## Phase 1 — Coverage & Data Integrity

**Goal:** Screen a broad, representative universe automatically. Fix the most significant gap: we only know about stocks someone has manually added.

**Why first:** Discovery is the highest-leverage improvement. An automated universe means the screener runs over 500+ stocks weekly instead of 41 manually curated ones. All subsequent phases assume a broader, self-updating ticker set.

### 1a. Universe Expansion ✓ Complete

Pull constituent lists from ETF holdings — SPY, QQQ, VGT, XLV, XLI, SOXX.

- `scripts/build_universe.py` — fetches S&P 500 + NASDAQ-100 from Wikipedia, SOXX from iShares CSV, XLV/XLI/VGT via yfinance top holdings
- `universe` table in DB — 537 active tickers; manual tickers preserved with `source='manual'`
- `refresh.py --universe --stale-days N` — refreshes all active universe tickers, skipping recently refreshed

**Result:** 537-ticker universe. Screener now surfaces 213 passing tickers (20A / 123B / 70C) vs 19 previously on 41 tickers.

### 1b. Automated Weekly Run

A single shell script chains the full pipeline: universe → refresh → screen → validate → build.

- `scripts/run_weekly.sh`
- Validate step gates the build: if `validate.py` exits 1, the build does not run
- Output: a dated log file in `logs/` for audit

**Milestone:** One command refreshes and publishes the full site with no manual steps.

### 1c. Momentum Overlay ✓ Complete

90-day relative price momentum computed for every screened ticker.

```
momentum_90d       = (price_today / price_90d_ago) - 1
relative_momentum  = momentum_90d - spy_momentum_90d
```

- SPY added as benchmark ticker with 501 days of price history
- `momentum_90d` and `relative_momentum` stored in `screen_results`
- Dashboard: "Momentum" toggle button reveals `vs SPY (90d)` column, colour-coded, re-sorts table

**Result:** Dashboard sortable by 90-day relative momentum. Top movers: ARM +54.7%, ANET +23.5%, AMD +17.1% vs SPY.

### 1d. Second-Source Cross-Check

After each refresh, pull market cap, revenue TTM, and trailing P/E from a second free API (Financial Modeling Prep, free tier: 250 req/day) and compare against yfinance values. Flag discrepancies above 10% as warnings in `data_audit`.

**Rationale:** `validate.py` catches internal inconsistencies. Cross-checking catches cases where yfinance returns a plausible but wrong value — stale data, wrong currency, corporate action not yet reflected.

**Status:** Deferred — requires FMP API key setup.

**Milestone:** `validate.py` reports cross-check warnings alongside internal checks. Zero cross-check failures on core Tier A tickers.

---

## Phase 2 — Discovery Pipeline

**Goal:** Surface emerging investment themes and candidate stocks from news data, without manual curation.

**Why second:** Phase 1 ensures the data layer is wide and clean. Phase 2 is meaningless without it — trending news means nothing if the candidate stocks are not already in the universe and screened.

### 2a. Broad News Feed

Integrate NewsAPI (free tier: 100 req/day, 1-month history) to pull daily business and technology headlines — not just per-ticker news, but the broad market conversation.

- New script: `scripts/news_broad.py`
- New table: `headlines (id, published_at, title, source, url, category)`
- Run daily; store and deduplicate by URL

**Milestone:** 30 days of broad headline history in the DB.

### 2b. Trend Clustering

Identify themes gaining coverage momentum by counting term frequency this week vs last week. No ML required — keyword frequency and growth rate surface the signal.

- New script: `scripts/trend_report.py`
- Count noun/noun-phrase frequency in `headlines` over rolling 7-day windows
- Output top 20 trending terms with growth rate
- Map terms to tickers via a maintained `THEME_MAP` dict
- Write output to `planning/trend-reports/YYYY-MM-DD.md`

**Milestone:** Weekly trend report generated automatically. At least 3 of the top 10 terms map to known tickers in the universe.

### 2c. Theme Map

A maintained dictionary mapping topic keywords to relevant tickers. This is the bridge between trend detection and the screener.

```python
THEME_MAP = {
    "quantum":       ["IONQ", "RGTI", "IBM", "MSFT", "GOOGL"],
    "GLP-1":         ["LLY", "NVO"],
    "semiconductor": ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
    "data centre":   ["NVDA", "ANET", "EQIX"],
    "nuclear":       ["CEG", "VST", "NNE"],
    "defence":       ["LMT", "RTX", "NOC", "GD"],
    "robotics":      ["ISRG", "ROK", "EMR"],
}
```

- Lives in `scripts/theme_map.py`
- Expanded continuously as new themes emerge
- Eventually replaceable with embedding similarity for more flexible matching

### 2d. Play Suggestion Engine

Given the trend report output, automatically draft play stubs for human review.

- New script: `scripts/suggest_plays.py`
- For each trending theme with at least 2 matching Tier A or B tickers: generate a play stub in `planning/play-suggestions/THEME-DATE.md`
- Stub includes: title, status (always `watch`), auto-generated summary, tickers, placeholder thesis
- Human reviews, writes the thesis, and promotes to `plays_data.py`

**Design constraint:** The engine drafts; humans decide. No play is published without a manually written thesis.

**Milestone:** At least one play in `plays_data.py` was originated from a suggestion file rather than from manual observation.

---

## Phase 3 — Analysis Depth

**Goal:** Make individual stock analysis more rigorous and self-contained. Reduce reliance on external sources for the analytical steps that can be scripted from existing data.

**Why third:** Broad discovery is only useful if the subsequent analysis is trustworthy. Phase 3 deepens the quality of output for stocks that have made it to the shortlist.

### 3a. Peer Comparison

For each screened ticker, show how its key metrics compare to the median of its industry peers in the universe.

- Compute industry-level medians for gross margin, net margin, fwd P/E, revenue growth, ROE
- Display as a comparison table on profile pages: "Company vs Industry Median"
- Highlight where a stock is materially above or below sector peers

**Rationale:** A 40% gross margin means very different things in software vs retail. Peer context makes the screener score more interpretable.

**Milestone:** Every profile page shows a peer comparison table. The dashboard can filter to "above industry median" on key metrics.

### 3b. Historical Score Tracking

Store a timestamped snapshot of each ticker's screener score and tier after every run. Plot the score trend on the profile page.

- New table: `score_history (ticker, run_date, score, tier, score_growth, score_profitability, score_valuation, score_balance_sheet)`
- Currently `screen_results` is overwritten each run — change to append
- Show score trend as a simple sparkline on profile pages

**Rationale:** A Tier B stock whose score has risen from 52 to 68 over three quarters is more interesting than one sitting flat at 63. Trend matters.

**Milestone:** Profile pages show a 6-quarter score history. Dashboard can filter to "improving score" tickers.

### 3c. Scripted DCF

A simple 5-year discounted cash flow model driven by DB values, with user-adjustable assumptions.

- Inputs from DB: revenue TTM, FCF margin, revenue CAGR (3yr), total shares outstanding
- User assumptions (hardcoded per ticker in a config dict): revenue growth rate, terminal growth rate, discount rate
- Output: intrinsic value per share, margin of safety vs current price
- Displayed on profile and report pages as a supplementary valuation section

**Scope note:** This is a sanity-check tool, not a prediction. The output is as good as the growth assumption. The purpose is to make the valuation judgment explicit and traceable, not to automate it.

**Milestone:** DCF section on Tier A report pages. Assumptions are visible alongside the output.

### 3d. Earnings Signal Detection

Monitor SEC EDGAR 10-Q filings for language signals in the Management Discussion section. Compare term frequency this quarter vs last quarter.

- Pull 10-Q filings via SEC EDGAR full-text search API (free)
- Flag tickers where language around "demand", "backlog", "guidance", "accelerating" increases materially
- Surface as a signal badge on profile pages: "Positive language shift in latest 10-Q"

**Milestone:** At least Tier A tickers have earnings signal badges. One signal is independently verifiable against the actual filing.

### 3e. Narrative Labelling

Add explicit AI-generated content labels to every prose section of analysis reports. Inline citations link figures stated in narrative text to the corresponding DB value on the profile page.

- Add `<div class="ai-generated">` wrapper with "Analysis: Claude Sonnet 4.6 · [date]" label
- Where narrative text cites a specific figure (e.g. "revenue grew 65%"), link to the profile page anchor showing that field
- Add to `generate_reports.py` generation workflow

**Rationale:** A reader should never have to wonder whether a number in the prose was pulled from data or written from memory. The citation makes the claim verifiable in one click.

---

## Phase 4 — Portfolio & Monitoring

**Goal:** Close the loop between research and actual positions. Track what was decided, when, at what price, and how it has performed against the original thesis.

**Why last:** This phase only has value once there are real positions to track. Building it earlier would be optimising for a problem that doesn't yet exist.

### 4a. Portfolio Page

Track live positions: ticker, entry date, entry price, current price, P&L, position size, target weight.

- New table: `portfolio (ticker, entry_date, entry_price, shares, target_weight, notes)`
- New page: `docs/portfolio.html`
- Shows unrealised P&L, weight vs target, days held
- Links each position to its analysis report and profile

### 4b. Thesis Tracking

Link each position to the report written at entry. Flag when the original thesis assumptions are no longer supported by the data.

- Store the report date alongside the portfolio entry
- On each weekly run: compare current fundamentals against the report-date snapshot
- Flag if revenue growth has decelerated materially, margin has compressed, or score has dropped a tier

**Rationale:** The decision to hold is as important as the decision to buy. A position should be reviewed when the thesis changes, not just when the price moves.

### 4c. Earnings Calendar

Show upcoming earnings dates for all held and watched tickers.

- Pull next earnings date from yfinance (`info.get("earningsTimestamp")`)
- Display on dashboard and portfolio page
- Mark tickers with earnings within 14 days

### 4d. Price Alerts (Optional)

Define price levels for watch-list tickers. Alert when a ticker hits a target entry price.

- Simple: store `(ticker, alert_price, direction)` in a config file
- Check on each weekly run; print alerts to terminal or a `logs/alerts.md` file
- Does not require any external notification service

---

## Deferred

Items that are interesting but depend on external setup or infrastructure not yet in place.

| Item | Dependency |
|------|-----------|
| GDELT / BigQuery integration | BigQuery account and project setup |
| Real-time price data | Paid data feed (yfinance is end-of-day) |
| Options flow analysis | Separate data source; out of scope for long-only portfolio |
| Mobile / push notifications | Would require a server; current architecture is static |
| Multi-user / shared access | Current architecture is personal and local |

---

## Summary Table

| Phase | Theme | Key Deliverable | Status |
|-------|-------|----------------|--------|
| 0 | Foundation | Screener, site, plays, 41 tickers | ✓ Complete |
| 1a | Universe Expansion | 537-ticker universe, ETF holdings pipeline | ✓ Complete |
| 1c | Momentum Overlay | 90-day vs-SPY signal, toggleable dashboard column | ✓ Complete |
| 1b | Weekly Automation | `run_weekly.sh` — one-command full pipeline | Next |
| 1d | Cross-Check | FMP second-source validation | Deferred (needs API key) |
| 2 | Discovery | News feed, trend clustering, play suggestion engine | Planned |
| 3 | Depth | Peer comparison, score history, DCF, earnings signals | Planned |
| 4 | Portfolio | Position tracking, thesis monitoring, earnings calendar | Planned |

---

## What Pythia Is Not

Defining the boundary matters as much as defining the roadmap.

- **Not a trading system.** No buy/sell execution, no order management, no real-time data.
- **Not a screener replacement.** The score is a starting point for research, not a ranking of stocks to buy in order.
- **Not a prediction engine.** DCF outputs, trend signals, and screener scores are inputs to human judgment — not outputs to act on mechanically.
- **Not a social or shared platform.** Personal research tool. No multi-user features are planned.
