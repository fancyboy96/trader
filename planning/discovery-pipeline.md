# Programmatic Stock & Play Discovery Pipeline

A design document and running to-do list for automating the process of surfacing promising stocks and investment themes.

---

## What We're Trying to Solve

Currently, tickers enter Pythia manually. A name comes from a news article, a conversation, or prior knowledge, and then we run the data pipeline on it. Plays are written by hand. This is fine for conviction ideas but it means we only ever see what we already know about.

The goal of this pipeline is to invert that: let data surface candidates we haven't thought of, then apply human judgment to the shortlist. The pipeline does not replace analysis. It produces a shortlist.

---

## Architecture Overview

The pipeline has five layers, each building on the previous:

```
1. Universe         — which tickers are eligible for screening
2. Data refresh     — fundamentals + prices pulled for the full universe
3. Screener         — hard filters + scoring, same as today
4. Signals          — momentum, news volume, trend clustering
5. Play suggestions — map signal clusters to candidate plays for review
```

Layers 1–3 are mostly mechanical extensions of what already exists. Layers 4–5 are the new work.

---

## Layer 1: Universe Expansion

### Problem

We screen 41 tickers. The S&P 500 has 503. The Russell 1000 has 1,000. We are missing a large fraction of the investable universe.

### Approach

Pull constituent lists from ETF holdings. ETFs are free, machine-readable, and already reflect a quality filter (inclusion criteria vary by ETF).

**Proposed starting universe (ETF overlap approach):**

| ETF | Focus | Size |
|-----|-------|------|
| SPY | Broad US market | ~503 tickers |
| QQQ | Nasdaq 100, tech-heavy | ~101 tickers |
| VGT | Information technology sector | ~300 tickers |
| XLV | Healthcare sector | ~60 tickers |
| XLI | Industrials sector | ~80 tickers |
| SOXX | Semiconductors | ~30 tickers |

Union of all six gives roughly 700–800 unique tickers. That is a manageable full-universe screen.

### Implementation

- Use `yfinance` to pull ETF holdings: `yf.Ticker("SPY").get_holdings()` — returns a DataFrame of ticker + weight
- Alternatively, download CSV holdings from ETF provider pages (iShares, Vanguard, State Street all publish these)
- Store in a new `universe` table: `(ticker TEXT, source TEXT, weight REAL, added_date TEXT)`
- New script: `scripts/build_universe.py` — pulls ETF holdings, upserts into `universe`, prints summary

### Notes

- The `universe` table is additive — tickers are never removed automatically, only marked inactive
- Manually added tickers (like IONQ, RGTI) should also be stored in `universe` with `source = 'manual'`
- `refresh.py --universe` flag to refresh all tickers in the universe table in batches

---

## Layer 2: Scheduled Refresh

### Problem

`refresh.py` is run manually. For a 700-ticker universe, a full refresh takes time and needs to be batched to avoid rate limits.

### Approach

- Batch refresh: process tickers in groups of 50, with a short sleep between batches
- Skip tickers refreshed within the last N days (configurable, default 7)
- Log refresh timestamps to a `refresh_log` table: `(ticker, refreshed_at, status)`
- New flag: `python scripts/refresh.py --universe --stale-days 7`

### Implementation

- Add `refresh_log` table to `db.py`
- Add `--stale-days` filter: only refresh tickers where `last_updated < today - N days`
- Add `--batch-size` flag with sleep between batches (default: 50 tickers, 2s sleep)
- Consider a shell wrapper script `scripts/run_weekly.sh` that chains refresh → screen → build

---

## Layer 3: Screener at Scale

### Problem

`screen.py` already works correctly. At 700 tickers, the filtering math is fast (pure SQL). The only issue is that a 700-ticker universe will produce many more Tier A/B results than we can act on.

### Approach

- No changes needed to the scoring logic
- Add a `--top-n` flag to display only the top N passing tickers
- Add a `min_score` column filter: `--min-score 60` to see only tickers above a threshold
- The dashboard already handles large result sets — the grouping UI helps navigate them

---

## Layer 4: Signals

This is the new work. Signals augment the fundamental score with real-time and trend data.

### 4a. Momentum Score

**What it is:** A price momentum measure — how much a stock has outperformed the market over the last 90 days.

**Why it matters:** Fundamental quality tells you what to own; momentum tells you when. A Tier A stock with accelerating momentum is a better near-term entry than a Tier A stock in a downtrend.

**Formula:**
```
momentum_90d = (price_today / price_90d_ago) - 1
relative_momentum = momentum_90d - spy_momentum_90d
```

**Implementation:**
- Already have 2 years of prices in the `prices` table — no new data needed
- Add `momentum_90d` and `relative_momentum` columns to `screen_results`
- Compute in `screen.py` from existing price rows
- Display on dashboard as an optional column (hidden by default, toggle-able)

**Effort:** Low. All data exists.

### 4b. News Volume Signal

**What it is:** A count of news items per ticker over the last 30 days, normalised by the ticker's typical news volume (z-score). A spike indicates unusual attention — earnings, catalyst, or risk event.

**Why it matters:** A stock with a high fundamental score and a news spike deserves a closer look faster than one that has been quiet.

**Implementation:**
- Already have a `news` table with `published_at` per ticker
- Add `news_30d_count` and `news_volume_zscore` to `screen_results`
- Compute in `screen.py` using a 90-day rolling window to establish a baseline
- Requires `news.py` to be run regularly on the full universe (add to weekly run script)

**Effort:** Low to medium. Requires `news.py` to be run at scale; yfinance news is free but limited.

### 4c. Trend Clustering from Headlines

**What it is:** Group recent news headlines by topic to identify themes gaining coverage momentum. A theme cluster that is growing rapidly (more articles this week than last) is a candidate play.

**Why it matters:** This is how plays should be discovered — not by waiting for a human to notice a trend, but by watching what the news is talking about at scale.

**Implementation approach (simple — no ML required):**

1. Pull N recent headlines from a news API (NewsAPI is the easiest starting point)
2. Tokenise headlines — remove stopwords, keep nouns and noun phrases
3. Count term frequency this week vs last week — terms with the highest growth rate are trending
4. Map trending terms to sectors/industries using a predefined keyword dictionary
5. Surface the mapping as a "trend report" page in the site

**Example keyword → sector mapping:**
```python
THEME_MAP = {
    "quantum": ["IONQ", "RGTI", "IBM", "MSFT", "GOOGL"],
    "GLP-1": ["LLY", "NVO"],
    "semiconductor": ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
    "data centre": ["NVDA", "ANET", "EQIX"],
    "nuclear": ["CEG", "VST", "NNE"],
}
```

Over time this map grows and is refined. Eventually it can be replaced with embedding similarity.

**Dependencies:**
- NewsAPI key (free tier: 100 req/day, 1-month archive) — easiest to start
- Alternatively: Polygon.io news endpoint (richer metadata, paid)
- Or: aggregate yfinance news across all universe tickers (free, but patchy)

**Effort:** Medium. NewsAPI integration is a day of work. The keyword map is ongoing curation.

---

## Layer 5: Play Suggestion Engine

**What it is:** A script that reads the trend cluster output and the screener results, then generates a draft play stub for human review.

**How it works:**

1. Take the top trending themes from Layer 4c
2. For each theme, find screener tickers that match (via the keyword → ticker map)
3. For each matching ticker, look up their tier and score
4. If the theme has at least 2 tickers with Tier A or B, generate a play stub:
   - Title: the theme name
   - Status: `watch` (always starts as watch — human promotes to active)
   - Summary: auto-generated one-liner from headline frequency data
   - Tickers: the matching set
   - Thesis: placeholder (`TODO: write thesis`)

5. Write the stub to a `planning/play-suggestions/THEME-DATE.md` file for manual review
6. Human reviews, edits the thesis, and adds it to `plays_data.py` when ready

**This is the key design principle:** the pipeline surfaces and drafts; humans decide and publish.

**Effort:** Medium. Depends on Layers 4a–4c being in place first.

---

## Data Dependencies

| Layer | New data needed | Source | Cost |
|-------|----------------|--------|------|
| Universe | ETF holdings | yfinance or ETF CSV | Free |
| Momentum | Nothing — prices already in DB | — | — |
| News volume | More news per ticker | yfinance (free, patchy) or NewsAPI | Free tier |
| Trend clustering | Broad headline feed | NewsAPI | Free (100 req/day) |
| Earnings signals | Transcripts or 10-Q text | SEC EDGAR API | Free |

Start with what costs nothing: momentum (data already exists) and news volume (yfinance news, already partially in DB).

---

## Running To-Do List

### Phase 1 — Universe & Data Foundation

- [ ] Create `scripts/build_universe.py`
  - Pull SPY, QQQ, VGT, XLV, XLI, SOXX holdings via yfinance or ETF provider CSV
  - Upsert into new `universe` table in `trader.db`
  - Print summary: total tickers by source, overlap count
- [ ] Add `universe` table to `db.py`
- [ ] Add `refresh_log` table to `db.py`
- [ ] Update `refresh.py` with `--universe` and `--stale-days` flags
- [ ] Test full-universe refresh on a sample of 50 tickers
- [ ] Create `scripts/run_weekly.sh`: chains build_universe → refresh --universe --stale-days 7 → screen → build_site

### Phase 2 — Momentum Overlay

- [ ] Add `momentum_90d` and `relative_momentum` to `screen_results` table
- [ ] Compute momentum in `screen.py` from existing `prices` table
  - Pull SPY prices for benchmark (need to add SPY to universe as benchmark)
  - Compute 90-day return for each ticker and for SPY
  - Store relative momentum in `screen_results`
- [ ] Add momentum as a toggleable column in the dashboard table
- [ ] Add momentum to the profile page snapshot grid
- [ ] Update `screening-criteria.md` to document the new signal

### Phase 3 — News & Trend Pipeline

- [ ] Sign up for NewsAPI (free tier)
- [ ] Store API key in a `.env` file (add `.env` to `.gitignore`)
- [ ] Create `scripts/news_broad.py`
  - Pull top business + technology headlines daily from NewsAPI
  - Store in a new `headlines` table: `(id, published_at, title, source, url, category)`
- [ ] Create `scripts/trend_report.py`
  - Count term frequency in `headlines` over rolling 7-day vs prior 7-day window
  - Output top 20 trending terms with growth rate
  - Map terms to tickers via `THEME_MAP` dict
  - Write output to `planning/trend-report-YYYY-MM-DD.md`
- [ ] Create `THEME_MAP` in `scripts/theme_map.py` — keyword → ticker list
  - Seed with quantum, GLP-1, semiconductor, AI, data centre, nuclear, defence, robotics
- [ ] Add a Trends page to the static site (optional, later)

### Phase 4 — Play Suggestion Engine

- [ ] Create `scripts/suggest_plays.py`
  - Read latest `trend-report-*.md` output
  - Match trending themes to tickers via `THEME_MAP`
  - Filter to tickers with Tier A or B in `screen_results`
  - For each qualifying theme, generate a play stub in `planning/play-suggestions/`
- [ ] Define stub format and review workflow (human reads stub, edits, promotes to `plays_data.py`)
- [ ] Add `play-suggestions/` to `.gitignore` or keep as untracked working files

### Phase 5 — Earnings Signals (Later)

- [ ] Research SEC EDGAR full-text search API
- [ ] Pull 10-Q management discussion sections for Tier A tickers
- [ ] Build a simple keyword frequency diff: this quarter vs last quarter
  - Flag tickers where language around "demand", "backlog", "guidance raised" increases
- [ ] Surface as a signal column in the dashboard

### Ongoing

- [ ] Expand `THEME_MAP` as new themes emerge
- [ ] Review `play-suggestions/` weekly and promote good ones to `plays_data.py`
- [ ] Tune screener thresholds annually against outcomes
- [ ] Add outcome tracking: when a position is taken, record entry price and date for later review

---

## What This Does Not Do

- It does not make buy/sell decisions. Every play requires a human thesis.
- It does not replace reading filings, earnings calls, or news directly.
- It does not guarantee the screener catches every good stock — it catches stocks that look good on the metrics we have defined.
- The trend clustering is keyword-based to start. It will miss nuanced themes and produce false positives. Human review is the filter.
