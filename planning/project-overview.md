# Pythia — Project Overview

A personal long-term equity research tool. Pythia screens stocks by fundamental quality, surfaces thematic investment plays, and publishes findings as a static website on GitHub Pages. It is a research aid, not a trading system.

---

## Contents

1. [Goal](#goal)
2. [Philosophy](#philosophy)
3. [Architecture](#architecture)
4. [Data Layer](#data-layer)
5. [Research Process](#research-process)
6. [Screener](#screener)
7. [Plays](#plays)
8. [Static Site](#static-site)
9. [File Layout](#file-layout)
10. [Scripts Reference](#scripts-reference)
11. [Running the Pipeline](#running-the-pipeline)
12. [Standards and Style](#standards-and-style)
13. [Backlog and Roadmap](#backlog-and-roadmap)

---

## Goal

Build a long-term equity portfolio of 10–20 positions with a 3–5 year holding horizon. Candidates are identified through:

1. Fundamental quality screening — revenue growth, profitability, valuation, balance sheet strength
2. Thematic research — identifying macro trends and mapping them to well-positioned companies
3. Ongoing monitoring — news, earnings signals, and momentum

The output is a set of HTML reports and a screener dashboard, published at `https://fancyboy96.github.io/trader/`.

---

## Philosophy

**Screening is a shortlist tool.** A high screener score does not mean buy. It means a company is worth deeper investigation. Every position requires a human thesis — a reason to own this stock at this price — before capital is committed.

**Quality over quantity.** The screener filters hard before scoring. A company that cannot generate free cash flow, has excessive debt, or is below minimum scale is excluded before any points are awarded.

**Fundamental first, momentum second.** Business quality is the primary filter. Price momentum is a timing signal layered on top — not a reason to buy.

**Plays lead; screens confirm.** Investment themes (plays) identify which areas to look at. The screener then finds the best-scoring companies within those areas. A stock can appear on the dashboard without being part of a play, but every play should have screener support.

**Every A-tier result gets a report.** Tier A tickers (score ≥ 75) receive a full HTML analysis report with thesis, moat assessment, tailwinds, risks, and a verdict. Tier B/C results get a profile page with metrics. The distinction matters: reports are judgments, profiles are data.

---

## Architecture

```
Data Sources                  Scripts                    Outputs
─────────────────────         ─────────────────────      ───────────────────────
yfinance (free)          →    refresh.py             →   trader.db (SQLite)
                              news.py                →   trader.db (news table)
                              screen.py              →   trader.db (screen_results)
trader.db                →    build_site.py          →   docs/ (static site)
plays_data.py            →    build_site.py          →   docs/plays/*.html
trader.db + NARRATIVES   →    generate_reports.py    →   docs/reports/*.html
                              
docs/                    →    GitHub Pages           →   public website
```

Everything is driven by Python scripts and a single SQLite database. No web framework, no build tool, no dependencies beyond `yfinance`, standard library, and Python f-strings for HTML generation.

---

## Data Layer

### Database: `data/trader.db`

A single SQLite file. All tables use `ON CONFLICT ... DO UPDATE` upserts so scripts are safe to re-run.

#### Tables

**`companies`** — one row per ticker, updated on each refresh.

| Column | Type | Notes |
|--------|------|-------|
| ticker | TEXT PK | |
| name | TEXT | Long name from yfinance |
| sector | TEXT | e.g. Technology |
| industry | TEXT | e.g. Semiconductors |
| country | TEXT | |
| description | TEXT | Business summary |
| website | TEXT | |
| last_updated | TEXT | ISO date |

**`fundamentals`** — one row per ticker per snapshot date. Allows historical tracking of ratio changes.

| Column | Type | Notes |
|--------|------|-------|
| ticker | TEXT | |
| snapshot_date | TEXT | ISO date, PK with ticker |
| market_cap | REAL | |
| enterprise_value | REAL | |
| revenue_ttm | REAL | Trailing twelve months |
| gross_profit_ttm | REAL | |
| operating_income_ttm | REAL | |
| net_income_ttm | REAL | |
| ebitda | REAL | |
| free_cashflow | REAL | |
| total_debt | REAL | |
| total_equity | REAL | |
| eps_ttm | REAL | |
| pe_ratio | REAL | Trailing P/E |
| fwd_pe | REAL | Forward P/E |
| ev_ebitda | REAL | |
| price_to_fcf | REAL | Derived: market_cap / free_cashflow |
| peg_ratio | REAL | |
| roe | REAL | Return on equity |
| gross_margin | REAL | As decimal, e.g. 0.73 |
| net_margin | REAL | |
| operating_margin | REAL | |
| debt_to_equity | REAL | As ratio (yfinance returns as %; stored divided by 100) |
| current_ratio | REAL | |
| beta | REAL | |
| dividend_yield | REAL | |

**`prices`** — daily OHLCV, 2-year rolling window.

| Column | Type |
|--------|------|
| ticker | TEXT |
| date | TEXT (PK with ticker) |
| open, high, low, close | REAL |
| volume | INTEGER |

**`income_annual`** — annual income statement rows, up to 4 fiscal years per ticker.

| Column | Type |
|--------|------|
| ticker | TEXT |
| fiscal_year | TEXT (PK with ticker) |
| revenue, gross_profit, operating_income, net_income, ebitda, eps | REAL |

**`news`** — headlines and summaries per ticker.

| Column | Type |
|--------|------|
| id | TEXT PK |
| ticker | TEXT |
| published_at | TEXT |
| title, summary, source, url | TEXT |
| sentiment | TEXT | NULL / positive / negative / neutral |

**`screen_results`** — one row per ticker, overwritten on each screen run.

| Column | Type |
|--------|------|
| ticker | TEXT PK |
| run_date | TEXT |
| passed_filters | INTEGER (0/1) |
| filter_fail_reason | TEXT |
| score | REAL (0–100) |
| tier | TEXT (A/B/C/D) |
| score_growth, score_profitability, score_valuation, score_balance_sheet | REAL |
| revenue_growth_yoy, revenue_cagr_3y, eps_growth_yoy | REAL |

### Known Data Quirks

- **`debt_to_equity` from yfinance** is returned as a percentage (e.g. 7.255 means 7.255%, not 7.255×). `refresh.py` divides by 100 on storage.
- **`total_equity` from yfinance** `bookValue` is per-share, not total. The screener uses `debtToEquity` directly from the API rather than computing it.
- **TSM revenue** is reported in New Taiwan Dollars. Figures in the DB and reports use approximate USD conversions noted in context.
- **yfinance news format** changed: items are now wrapped in `item['content']`. `news.py` handles this.

---

## Research Process

```
Identify theme/candidate
        ↓
refresh.py TICKER          ← pull fundamentals, prices, income statement
news.py TICKER             ← pull recent headlines
screen.py                  ← score all tickers, update screen_results
build_site.py              ← regenerate all HTML
generate_reports.py        ← regenerate Tier A analysis reports
        ↓
Review profile page and screener score
        ↓
If Tier A: write/review narrative in generate_reports.py → NARRATIVES dict
If Tier B/C: add to a play if thematically relevant
        ↓
git add docs/ && git push  ← publish
```

---

## Screener

Defined in full in `planning/screening-criteria.md`. Summary:

### Hard Filters (must pass all)

| Filter | Threshold |
|--------|-----------|
| Market cap | ≥ $2B |
| Revenue TTM | ≥ $500M |
| Gross margin | ≥ 30% |
| Debt / equity | ≤ 2.0 |
| Current ratio | ≥ 1.0 |
| Free cash flow | > 0 |

### Scoring (0–100 pts)

| Category | Max pts |
|----------|---------|
| Growth (Rev YoY, Rev CAGR 3yr, EPS YoY) | 30 |
| Profitability (Gross margin, Net margin, ROE) | 25 |
| Valuation (Fwd P/E, PEG, FCF yield) | 25 |
| Balance sheet (D/E, Current ratio, FCF positive) | 20 |

### Tiers

| Score | Tier | Action |
|-------|------|--------|
| 75–100 | A | Full analysis report |
| 50–74 | B | Watch — profile page |
| 25–49 | C | Weak — profile page |
| 0–24 | D | Exclude |

---

## Plays

Plays are curated thematic investment ideas. A play asserts that a macro trend creates a structural tailwind for a set of companies.

### Structure

Each play lives in `scripts/plays_data.py` as a Python dict:

```python
{
    "id":      "url-safe-slug",
    "title":   "Display Name",
    "status":  "active",          # active | watch | closed
    "summary": "One-line for index table",
    "thesis":  "Full rationale...",
    "tickers": ["AAPL", "MSFT"],  # must be in DB
    "added":   "2026-04-18",
}
```

### Current Plays

| Play | Status | Tickers |
|------|--------|---------|
| AI Infrastructure | Active | NVDA, AVGO, TSM, ANET |
| GLP-1 & Metabolic Health | Active | LLY, DXCM |
| Clean Energy Transition | Watch | FSLR |
| Quantum Computing | Watch | MSFT, GOOGL, IBM, IONQ, RGTI, QBTS |

### Status Definitions

| Status | Meaning |
|--------|---------|
| Active | Conviction idea — ready to research for entry |
| Watch | Promising but a condition must be met first: a price level, a catalyst, or more data |
| Closed | Thesis played out or invalidated |

### Adding a Play

See `planning/how-to-add-a-play.md` for step-by-step instructions.

---

## Static Site

Published at `https://fancyboy96.github.io/trader/` from the `docs/` folder on `main`.

### Pages

| URL | Description |
|-----|-------------|
| `index.html` | Landing page with nav cards and at-a-glance stats |
| `plays.html` | Plays index — table of all plays |
| `plays/{id}.html` | Play detail — thesis and stock table |
| `dashboard.html` | Screener results — all tickers with grouping controls |
| `methodology.html` | Scoring criteria and tier definitions |
| `profiles/{TICKER}.html` | Company profile — snapshot, score breakdown, news |
| `reports/{TICKER}-{DATE}.html` | Full analysis report (Tier A only) |

### Design System

Defined in `_shared/standards.md`. Key points:
- CSS custom properties for light/dark theming; `localStorage` for persistence across pages
- No JavaScript framework — all interactivity is vanilla JS in `<script>` blocks
- Theme toggle on every page; flash-free via a `THEME_INIT` script in `<head>`
- Font: Helvetica Neue / Arial, 15px base, 1.65 line height, max-width 1100px

### Generating the Site

```bash
python3 scripts/build_site.py        # all site pages
python3 scripts/generate_reports.py  # Tier A analysis reports
git add docs/ && git push            # publish
```

---

## File Layout

```
trader/
├── data/
│   └── trader.db                    ← SQLite database (not in git)
├── docs/                            ← GitHub Pages root
│   ├── index.html
│   ├── plays.html
│   ├── dashboard.html
│   ├── methodology.html
│   ├── plays/
│   │   └── {id}.html
│   ├── profiles/
│   │   └── {TICKER}.html
│   └── reports/
│       └── {TICKER}-{DATE}.html
├── planning/
│   ├── project-overview.md          ← this file
│   ├── screening-criteria.md        ← screener source of truth
│   ├── discovery-pipeline.md        ← programmatic discovery design + to-do
│   ├── how-to-add-a-play.md         ← step-by-step play workflow
│   ├── naming.md                    ← product naming rationale
│   └── watchlist.md                 ← candidate tracking
├── scripts/
│   ├── db.py                        ← schema + connection helper
│   ├── refresh.py                   ← pull fundamentals + prices via yfinance
│   ├── news.py                      ← pull headlines via yfinance
│   ├── screen.py                    ← run screener, write screen_results
│   ├── build_site.py                ← generate all static HTML
│   ├── generate_reports.py          ← generate Tier A analysis reports
│   └── plays_data.py                ← curated plays registry
└── _shared/
    └── standards.md                 ← prose style + design system (shared with Orbit)
```

---

## Scripts Reference

### `refresh.py`

Pull fundamentals, 2-year price history, and annual income statements for one or more tickers.

```bash
python3 scripts/refresh.py NVDA AAPL          # specific tickers
python3 scripts/refresh.py --all              # all tickers in companies table
```

**Key behaviour:**
- Upserts into `companies`, `fundamentals`, `prices`, `income_annual`
- Safe to re-run; overwrites same-date snapshots
- `debt_to_equity` divided by 100 on write (yfinance quirk)

### `news.py`

Pull recent headlines for one or more tickers via yfinance.

```bash
python3 scripts/news.py NVDA AAPL
python3 scripts/news.py --all
```

### `screen.py`

Score all tickers in the database and write results to `screen_results`.

```bash
python3 scripts/screen.py                     # run, display Tier B and above
python3 scripts/screen.py --min-tier D        # show all tiers
python3 scripts/screen.py --verbose           # show score breakdown per ticker
```

### `build_site.py`

Generate all static HTML pages into `docs/`.

```bash
python3 scripts/build_site.py
```

Reads from `trader.db` and `plays_data.py`. Overwrites all files in `docs/` on each run.

### `generate_reports.py`

Generate full analysis reports for Tier A tickers. Narratives are hardcoded in the `NARRATIVES` dict at the top of the file.

```bash
python3 scripts/generate_reports.py
```

### `plays_data.py`

Not a script — a data file. Edit directly to add, update, or close plays. Then run `build_site.py` to publish.

---

## Running the Pipeline

### Full refresh and publish

```bash
python3 scripts/refresh.py --all
python3 scripts/news.py --all
python3 scripts/screen.py
python3 scripts/build_site.py
python3 scripts/generate_reports.py
git add docs/ && git commit -m "Weekly refresh $(date +%Y-%m-%d)" && git push
```

### Add a new ticker

```bash
python3 scripts/refresh.py TICKER
python3 scripts/news.py TICKER
python3 scripts/screen.py
python3 scripts/build_site.py
git add docs/ && git push
```

### Add a new play

1. Edit `scripts/plays_data.py`
2. Run `python3 scripts/build_site.py`
3. Push — see `planning/how-to-add-a-play.md` for full steps

---

## Standards and Style

Prose style and the HTML design system are defined centrally in `_shared/standards.md` (shared with the Orbit project).

Key prose rules:
- No em-dashes in prose — replace with parentheses or restructure the sentence
- No contrast framing ("not X" as the rhetorical payoff) — state the affirmative fact
- Lead with subject and fact; subordinate clauses follow
- Anchor percentages to their denominator on first reference

Key design rules:
- All colours are CSS custom properties; light mode default, dark mode via `[data-theme="dark"]`
- Theme stored in `localStorage` under key `pythia-theme`
- A minified theme-restore script runs in `<head>` to prevent flash on load

---

## Backlog and Roadmap

Full detail in `planning/discovery-pipeline.md`. Summary:

### Near-term

- [x] Data validation script (`scripts/validate.py`) — sanity checks on fundamentals, prices, income, and audit log after every refresh
- [x] Source attribution — fetch date and snapshot date shown on every profile page and analysis report; data provenance line links back to raw profile from report
- [x] `data_audit` table — every yfinance API call logged with timestamp, endpoint, rows returned, and status
- [ ] Universe expansion — pull S&P 500 / ETF constituent lists, screen the full universe automatically
- [ ] Scheduled refresh script — batch refresh stale tickers weekly
- [ ] Momentum overlay — add 90-day relative momentum to screener scores using existing price data

### Medium-term

- [ ] NewsAPI integration — broad headline feed for trend detection
- [ ] Trend clustering — keyword frequency analysis to surface emerging themes
- [ ] `THEME_MAP` — curated keyword → ticker mapping for automatic play candidate matching

### Later

- [ ] Play suggestion engine — auto-draft play stubs from trend output for human review
- [ ] SEC EDGAR integration — earnings signal detection from 10-Q management discussion sections
- [ ] Outcome tracking — record entry prices when positions are taken, review against thesis

### Deferred

- [ ] Second-source cross-check — pull the same key metrics (market cap, revenue, P/E) from a second free API (Financial Modeling Prep or Alpha Vantage) after each refresh and flag discrepancies above a threshold; catches silent yfinance data errors that pass internal consistency checks
- [ ] Narrative labelling — add an explicit "Analysis written by Claude [model version]" label to each section of analysis reports that contains AI-generated prose; inline citations linking figures in the narrative to the corresponding DB value on the profile page
- [ ] GDELT / BigQuery — broad news event database; requires BigQuery account setup
- [ ] DCF model — scripted discounted cash flow from loaded financials
- [ ] Portfolio page — track live positions, P&L, and weighting vs targets
