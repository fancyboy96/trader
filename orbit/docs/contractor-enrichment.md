# Contractor Enrichment Pipeline

## Purpose

We have 34,533 contractors in the database — sourced from AusTender (federal) and SA CKAN (state). Beyond name and ABN, every enrichment field (description, website, address, capabilities, sector) is empty. This document defines a tiered pipeline to progressively enrich contractor records with structured data, news intelligence, and AI-generated summaries.

The goal is a database where the contractors that matter most (by spend, by sector relevance, by news activity) have enough context to support analysis, filtering, and monitoring — without burning API quota on long-tail noise.

---

## Contractor Landscape

| Spend tier | Contractors | Total value |
|---|---|---|
| >$1B | 38 | $101B |
| $100M–$1B | 266 | $73.6B |
| $10M–$100M | 1,296 | $38B |
| $1M–$10M | 4,187 | $13.5B |
| $100K–$1M | 11,524 | $3.7B |
| <$100K | 17,214 | $638M |

**24,439 of 34,533 contractors have ABNs** (from AusTender). SA CKAN contractors (659) have no ABNs — cross-reference deferred until SA Tenders scrape provides them.

The pipeline is tiered to match enrichment depth to contractor significance. Running every enrichment step against all 34k records would be noisy, slow, and wasteful — and most of the bottom 17k are one-off engagements that won't yield useful signals.

---

## Tiers

| Tier | Threshold | Count (approx) | Enrichment depth |
|---|---|---|---|
| **Tier 1** | >$10M total spend | ~1,600 | Full: ABN + GDELT + Claude |
| **Tier 2** | $1M–$10M | ~4,200 | ABN + GDELT (raw, no Claude) |
| **Tier 3** | $100K–$1M | ~11,500 | ABN only |
| **Tier 4** | <$100K | ~17,200 | Name/ABN as-is; no enrichment |

Tiers are recalculated at runtime from the contracts table — not hardcoded.

---

## Phase 1 — ABN Lookup Enrichment

**Target:** All contractors with an ABN (~24,400)  
**Source:** Australian Business Register (ABR) ABN Lookup API  
**Cost:** Free; requires a free GUID from `abr.business.gov.au`

### What it provides

| Field | ABR field | Mapped to |
|---|---|---|
| Legal name | `entityName` | `businesses.name` (if cleaner than current) |
| Entity type | `entityTypeCode` | `businesses.type` (mapped to schema enum) |
| State | `mainBusinessPhysicalAddress.stateCode` | `businesses.state` |
| Postcode | `mainBusinessPhysicalAddress.postcode` | (new field or address) |
| GST status | `goodsAndServicesTax` | `businesses.notes` |
| ABN status | `entityStatus` | `businesses.status` (inactive → set to inactive) |

### Entity type mapping

| ABR code | Orbit type |
|---|---|
| PRV (Australian Private Company) | `other` → `prime_contractor` or `sme` based on spend |
| PUB (Australian Public Company) | `prime_contractor` |
| IND (Individual/Sole Trader) | `sme` |
| TRT (Trust), PTR (Partnership) | `other` |
| GOV (Government Entity) | `government_agency` |

### API endpoint

```
https://abr.business.gov.au/json/AbnDetails.aspx?abn={abn}&guid={GUID}
```

Free GUIDs are issued at `https://abr.business.gov.au/Tools/WebServices`.

### Script: `scripts/abn_enrichment.py`

```
python3 scripts/abn_enrichment.py              # all contractors with ABN, Tier 1-3 only
python3 scripts/abn_enrichment.py --all        # all tiers including Tier 4
python3 scripts/abn_enrichment.py --abn 12345  # single ABN
python3 scripts/abn_enrichment.py --dry-run    # print without writing
```

Rate limit: no documented limit; 1 request/second is safe.

---

## Phase 2 — GDELT News Enrichment

**Target:** Tier 1 (~1,600 contractors >$10M) + Tier 2 (~4,200 contractors >$1M)  
**Source:** GDELT DOC 2.0 API (same endpoint as existing `gdelt_scan.py`)  
**Cost:** Free; rate-limited

This extends the existing GDELT scan from the curated `entities.json` list to the full contractor database. The approach differs from the current scan:

- **Current scan:** Small curated entity list with hand-crafted aliases and context terms (strategy 3)
- **Contractor enrichment scan:** Larger automated sweep using contractor names + ABN-derived clean names; lower signal quality but wider coverage

### Query construction

AusTender names are often ALL CAPS legal names (e.g. `BAE SYSTEMS AUSTRALIA PTY LTD`) that appear rarely in press. The query is built in two steps:

1. **Normalise the name** — title-case, strip legal suffixes (`PTY LTD`, `LIMITED`, `PTY LIMITED`) to get a short-form name
2. **Build query:**
   ```
   ("{full_legal_name}" OR "{short_name}") (Australia OR Australian) (contract OR government OR defence OR defense)
   ```
   If the contractor already has an entry in `entities.json`, use its aliases and context terms instead.

**Example — `LOCKHEED MARTIN AUSTRALIA PTY LTD`:**
```
("Lockheed Martin Australia Pty Ltd" OR "Lockheed Martin Australia") (Australia OR Australian) (contract OR government OR defence OR defense)
```

### Signal storage

GDELT results are stored in the existing `news_signals` and `news_signal_businesses` tables — no schema changes needed. The existing deduplication-by-URL logic prevents duplicate articles from being inserted across runs.

Contractors are linked to signals via `news_signal_businesses`. One article can be linked to multiple contractors (correct behaviour — an article may mention several companies).

### Rate limiting and batching

At 5 seconds per entity (current rate), scanning 5,800 Tier 1+2 contractors would take ~8 hours. This needs to run as a batched background job with checkpointing:

- Track last-scanned contractor by ABN in a `enrichment_runs` table (or a simple checkpoint file)
- Resume from checkpoint on interruption
- Run Tier 1 first, then Tier 2 in a separate pass

### CLI: extended `gdelt_scan.py` or separate `scripts/contractor_gdelt_scan.py`

```
python3 scripts/contractor_gdelt_scan.py             # Tier 1 + 2, default 30-day window
python3 scripts/contractor_gdelt_scan.py --tier 1    # Tier 1 only
python3 scripts/contractor_gdelt_scan.py --days 90   # longer window for initial backfill
python3 scripts/contractor_gdelt_scan.py --resume    # continue from checkpoint
python3 scripts/contractor_gdelt_scan.py --dry-run   # print queries, don't store
```

### Expected yield

Based on existing GDELT scan results for 10 defence entities over 14 days:
- Tier 1 (~1,600 contractors): most >$100M contractors will return at least some articles; smaller defence suppliers may return 0
- Tier 2 (~4,200 contractors): signal density drops significantly; most SMEs won't appear in press at all
- Approximate useful signal rate: ~20–30% of Tier 1 contractors will have ≥1 relevant article in a 30-day window

Zero-result contractors are expected and fine — the absence of press coverage is itself a data point (quiet company, sole-trader, foreign entity, etc.).

---

## Phase 3 — Claude Extraction Layer

**Target:** Tier 1 only (~1,600 contractors)  
**Requires:** Anthropic API key in `.env`  
**Cost:** Low–moderate depending on article volume

For each GDELT article linked to a Tier 1 contractor, Claude processes the article to extract:

| Field | Description |
|---|---|
| `relevance_score` | 1–10: how relevant is this to Australian government contracting |
| `summary` | 1–2 sentence plain-English summary |
| `key_insight` | The single most commercially significant fact in the article |
| `flags` | Array: `contract_win`, `contract_loss`, `financial_news`, `M&A`, `legal`, `personnel`, `capability_announcement` |
| `mentioned_businesses` | Other contractors mentioned — linked to their `businesses.id` if matched |
| `mentioned_programs` | Government programs mentioned |
| `contract_value_mentioned` | Dollar figure if a contract value is stated |

Articles with `relevance_score < 4` are discarded.

Additionally, once a contractor has ≥3 scored signals, Claude generates a **contractor profile** stored in `businesses.description`:

```
{contractor_name} is a {entity_type} providing {primary_services} to Australian government agencies.
Key contracts include {top_contracts_by_value}. Recent news: {key_insight_from_top_signal}.
```

This profile is regenerated whenever new high-relevance signals are added.

---

## Phase 4 — Supplementary Sources (future)

These are not in scope for the initial build but are the natural next enrichment sources once Phases 1–3 are complete:

| Source | Data | Method |
|---|---|---|
| SA Tenders (`tenders.sa.gov.au`) | ABNs for SA contractors, real contract numbers | Playwright scraper (built, pending site fix) |
| ASIC company search | Director names, share structure, company history | Scraping or third-party API |
| ASX announcements | Contract win/loss disclosures, earnings | ASX feed or GDELT |
| LinkedIn / company website | Employee count, office locations, capabilities | Web scrape (selective, top tier only) |
| ABN Lookup name history | Previous trading names — useful for M&A tracking | ABR API `historicalNameList` field |

---

## Data Model Changes Required

The current schema supports news signals and basic business fields. Enrichment adds:

```sql
-- Track enrichment runs per contractor (checkpoint + audit)
CREATE TABLE enrichment_runs (
  id            TEXT PRIMARY KEY,
  business_id   TEXT REFERENCES businesses(id),
  phase         TEXT CHECK(phase IN ('abn_lookup', 'gdelt', 'claude_profile')),
  status        TEXT CHECK(status IN ('complete', 'skipped', 'error')),
  result_summary TEXT,
  run_at        TEXT DEFAULT (datetime('now'))
);

-- Index for checkpoint queries
CREATE INDEX idx_enrichment_runs_biz_phase ON enrichment_runs(business_id, phase);
```

No changes to `businesses`, `news_signals`, or `news_signal_businesses` are required — existing fields cover all output.

---

## Build Order

1. **ABN Lookup script** (`scripts/abn_enrichment.py`) — no API key needed, immediate value, sets clean names used by GDELT queries
2. **Contractor GDELT scan** (`scripts/contractor_gdelt_scan.py`) — extends existing GDELT infra to contractor scale; run Tier 1 first
3. **Claude extraction pass** — activates once Anthropic API key is configured; can be run as a post-scan pass over existing raw signals
4. **Contractor profile generation** — final Claude step; generates `businesses.description` for Tier 1

---

## Open Questions

- **ABR GUID** — needs free registration at `abr.business.gov.au/Tools/WebServices`
- **Anthropic API key** — needed for Phase 3; Claude extraction is fully designed and can be activated without code changes
- **GDELT scan duration** — 8+ hours for full Tier 1+2 sweep; decide whether to run overnight or split across days
- **SA CKAN deduplication** — 659 SA contractors have no ABN; held until SA Tenders scrape (expected ~17 Apr 2026) provides ABNs for cross-reference
