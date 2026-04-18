# Screening Criteria

Defines the fundamental signals used by `scripts/screen.py` to rank and filter candidates. Update this file first when changing what the screener looks for; then update `screen.py` to match.

---

## Pass/Fail Filters

Hard cutoffs. A ticker that fails any of these is excluded before scoring.

| Filter | Condition | Rationale |
|---|---|---|
| Market cap | ≥ $2B | Avoid micro/small cap liquidity risk |
| Revenue (ttm) | ≥ $500M | Minimum business scale |
| Gross margin | ≥ 30% | Indicates some pricing power or moat |
| Debt / equity | ≤ 2.0 | Avoid overleveraged balance sheets |
| Current ratio | ≥ 1.0 | Basic solvency check |
| Free cash flow | > 0 | Must be generating cash, not just profit |

---

## Scoring Signals

Each signal contributes points to a total score (0–100). Signals are grouped by category. Weights reflect relative importance.

### Growth (30 pts)

| Signal | Points | Criteria |
|---|---|---|
| Revenue growth YoY | 0–10 | < 5% → 0, 5–15% → 5, > 15% → 10 |
| Revenue CAGR 3yr | 0–10 | < 5% → 0, 5–20% → 5, > 20% → 10 |
| EPS growth YoY | 0–10 | < 0% → 0, 0–15% → 5, > 15% → 10 |

### Profitability (25 pts)

| Signal | Points | Criteria |
|---|---|---|
| Gross margin | 0–10 | < 30% → 0, 30–50% → 5, > 50% → 10 |
| Net margin | 0–10 | < 5% → 0, 5–15% → 5, > 15% → 10 |
| Return on equity | 0–5 | < 10% → 0, 10–20% → 3, > 20% → 5 |

### Valuation (25 pts)

| Signal | Points | Criteria |
|---|---|---|
| Forward P/E | 0–10 | > 50 → 0, 25–50 → 5, < 25 → 10 |
| PEG ratio | 0–10 | > 3 → 0, 1.5–3 → 5, < 1.5 → 10 |
| FCF yield | 0–5 | < 1% → 0, 1–3% → 3, > 3% → 5 |

### Balance sheet (20 pts)

| Signal | Points | Criteria |
|---|---|---|
| Debt / equity | 0–10 | > 1.5 → 0, 0.5–1.5 → 5, < 0.5 → 10 |
| Current ratio | 0–5 | < 1.2 → 0, 1.2–2.0 → 3, > 2.0 → 5 |
| Free cash flow positive | 0–5 | Negative → 0, Positive → 5 |

---

## Output Tiers

| Score | Tier | Meaning |
|---|---|---|
| 75–100 | A | Strong candidate — proceed to full fundamental report |
| 50–74 | B | Watch — revisit if price pulls back or growth accelerates |
| 25–49 | C | Weak — pass unless there is a specific catalyst thesis |
| 0–24 | D | Exclude |

---

## Notes

- All ratios use the most recent snapshot in `fundamentals` table (latest `snapshot_date` per ticker).
- Revenue CAGR is computed from `income_annual` rows; requires at least 3 years of data. Tickers with fewer years score 0 on that signal rather than being excluded.
- PEG uses `fwd_pe / analyst_growth_est`. If `peg_ratio` is NULL in the db (yfinance doesn't always return it), that signal scores 0.
- Screening is a shortlist tool, not a buy signal. Every A-tier output still requires a manual fundamental report before any decision.
