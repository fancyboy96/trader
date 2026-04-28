# Orbit — News Signal Extraction Pipeline

## Purpose

A standalone, reusable data extraction pipeline that harvests news signals for any set of named entities (companies, programs, organisations) using GDELT, with optional Claude-powered relevance filtering.

This is not part of the web application. It runs independently as a CLI tool and writes to the local SQLite database. The same pipeline will later be wired into the app's admin-triggered GDELT scan.

---

## Part 1 — Entity Setup

This part covers how company and program data is defined and maintained. It is a one-time setup step, updated manually as new entities are added or aliases are refined.

### What is an Entity?

An entity is any named organisation, company, or defence program we want to monitor. Each entity has:

| Field | Description |
|---|---|
| `canonical_name` | The primary name — stored in the database, used as the display name throughout the app |
| `type` | `business` or `program` |
| `aliases` | Alternative names the entity is known by in news coverage |
| `context_terms` | Domain-specific words that improve query precision for ambiguous or short names |

**Why aliases matter:** GDELT indexes news exactly as written. "Hanwha Defense Australia" (official name) returned 0 results; adding the alias "Hanwha" returned 75. Aliases are not optional — they are the primary lever for coverage.

**Why context terms matter:** Short or ambiguous names like "NIOA" or "ASC" will match unrelated articles without additional constraint. Context terms act as a domain filter, e.g. adding `["submarine", "naval", "shipbuilding"]` to ASC ensures results are defence-relevant.

### Entity Config (`data/entities.json`)

All entities are defined in a single config file. The scan script reads this at runtime — no code changes needed to add or update entities.

Current seed set: **12 businesses + 4 programs** (see `data/entities.json` for the full live list). Illustrative examples:

```json
[
  {
    "canonical_name": "Hanwha Defense Australia",
    "type": "business",
    "aliases": ["Hanwha Defence Australia", "Hanwha Defence", "Hanwha"],
    "context_terms": ["Redback", "Huntsman", "LAND 400", "vehicle"]
  },
  {
    "canonical_name": "Thales Australia",
    "type": "business",
    "aliases": ["Thales", "THALES AUSTRALIA LIMITED", "Thales Australia Limited"],
    "context_terms": []
  },
  {
    "canonical_name": "TKMS Sonartech Atlas",
    "type": "business",
    "aliases": ["TKMS SONARTECH ATLAS PTY LIMITED", "Sonartech Atlas", "Atlas Elektronik Australia"],
    "context_terms": ["sonar", "submarine", "naval", "acoustic"]
  },
  {
    "canonical_name": "SSN-AUKUS",
    "type": "program",
    "aliases": ["AUKUS submarine", "nuclear submarine Australia", "SSN AUKUS"],
    "context_terms": []
  }
]
```

Aliases are not optional — they are the primary lever for GDELT coverage. AusTender supplier names often differ from news coverage names (e.g. "THALES AUSTRALIA LIMITED" in AusTender vs "Thales" in press). Both must be covered.

After each AusTender harvest, `data/unmatched_suppliers_YYYY-MM-DD.csv` lists all supplier names that did not match any entity. Review this file to identify new entities or missing aliases worth adding.

---

## Part 2 — News Signal Extraction (GDELT)

This part covers how entities from Part 1 are used to query GDELT and extract news signals. This runs on demand via the CLI.

### Query Construction

For each entity, a GDELT query is built as follows:

```
({canonical_name} OR {alias_1} OR {alias_2} ...) ({context_term_1} OR {context_term_2} ...)
```

If the entity has no context terms, the baseline context clause is applied:
```
(defence OR defense OR military OR contract)
```

**Example — Hanwha Defense Australia:**
```
("Hanwha Defense Australia" OR "Hanwha Defence Australia" OR "Hanwha Defence" OR "Hanwha") (Redback OR Huntsman OR "LAND 400" OR vehicle)
```

**Example — SSN-AUKUS (program, no context terms needed):**
```
("SSN-AUKUS" OR "AUKUS submarine" OR "nuclear submarine Australia" OR "SSN AUKUS") (defence OR defense OR military OR contract)
```

### GDELT API Parameters

| Parameter | Value | Rationale |
|---|---|---|
| `mode` | `artlist` | Returns article list with metadata |
| `maxrecords` | `75` | 25 (default) leaves results on the table |
| `timespan` | `{N}d` | Configurable, default 30 days |
| `format` | `json` | — |
| `sourcelang` | omitted by default | `english` available as a flag — marginal benefit in testing |
| `sourcecountry` | never used | `AU` returned 0 results in all tests; most defence coverage comes from international outlets |

### Deduplication

Articles are deduplicated by URL against existing `news_signals` records. If a URL already exists, the article is skipped for insertion but the business/program link is still created if not already present.

### Extraction Steps

```
1. Load entities from data/entities.json
2. For each entity:
   a. Build GDELT query
   b. Fetch articles (with retry on 429)
   c. Deduplicate by URL
   d. For each new article:
      i.  [If Claude key present] Send to Claude → extract structured signal
      ii. [If no key] Store raw headline + metadata, relevance_score = null
   e. Write to news_signals + junction tables
3. Update gdelt_scans record
```

### Claude Relevance Filtering

Raw GDELT results contain noise — articles that mention an entity name but are not relevant to Australian defence. Claude extraction filters this using the prompt in `docs/reqs.md` Appendix A.

| Field | Source |
|---|---|
| `summary` | Claude |
| `relevance_score` | Claude (1–10) |
| `flags` | Claude |
| `key_insight` | Claude |
| `mentioned_businesses` | Claude → matched against entity canonical names |
| `mentioned_programs` | Claude → matched against program entities |
| `contract_value_mentioned` | Claude |

Articles with `relevance_score < 4` are discarded and not stored. Without a key, all raw articles are stored and can be scored in a later pass.

### CLI Interface

```
python3 scripts/gdelt_scan.py [options]

Options:
  --days N          Timespan in days (default: 30)
  --entity NAME     Scan a single entity by canonical name
  --type TYPE       Scan all entities of type: business | program
  --dry-run         Print queries and result counts, do not write to DB
  --english-only    Add sourcelang:english filter to all queries
```

---

## Part 3 — Contract Data Extraction

Contract records are harvested separately from news signals. The pipeline targets Australian government tender and contract databases at federal and state level.

### Federal

| Source | Data available | Access method |
|---|---|---|
| AusTender OCDS API (`api.tenders.gov.au/ocds`) | Contract awards, values, agencies, contractors, ABNs, dates, UNSPSC codes | JSON API — primary source |

**The OCDS API is the access method.** It returns structured JSON per the Open Contracting Data Standard, includes supplier ABNs, and supports cursor pagination. Key characteristics confirmed in testing:

- Returns 100 records per page with a `links.next` cursor — break on empty batch to avoid hang
- No server-side agency filter — returns all-of-government contracts (this is intentional; we store everything)
- ~65,000–70,000 releases per year across all Commonwealth agencies
- Rate limit not documented; 1s delay between pages has been sufficient
- Date range query: `/findByDates/contractPublished/{start}/{end}` (ISO 8601)
- ABN is in `additionalIdentifiers[].id` where `scheme = "AU-ABN"`
- UNSPSC classification code is in `contracts[0].items[0].classification.id`
- Procurement method (open/limited) is in `tender.procurementMethod`

**Supplier deduplication:** check ABN first (most reliable); fall back to normalised name match. This handles the common case of one company appearing under multiple name variants across different contract notices.

**Pass-through accounts to be aware of:** Several high-value "suppliers" are financial channels for foreign government-to-government procurement (FMS Account Reserve Bank of Australia, Federal Reserve Bank NY, cooperative program accounts). These should be excluded from supplier analysis — see `docs/analysis-austender-limitations.md`.

### State — South Australia (primary)

| Source | Notes |
|---|---|
| SA Tenders & Contracts (`tenders.sa.gov.au`) | SA Government procurement; includes Defence SA contracts; no bulk export — requires scraping |
| Defence SA (`defencesa.com`) | Industry news and project updates; no structured contract feed; lower signal density |

### Other States (secondary)

Relevant where SA prime contractors have interstate subcontract relationships or where a contract has SA industry involvement.

| State | Source |
|---|---|
| WA | `tenders.wa.gov.au` |
| NSW | `tenders.nsw.gov.au` |
| VIC | `tenders.vic.gov.au` |
| QLD | `qtenders.epw.qld.gov.au` |

### Contract Extraction Approach

1. **AusTender OCDS API** — paginate with date range, parse each release, match supplier names against entity list using normalised name matching, store in `contracts` and `businesses` tables. Per-page commits ensure progress is never lost on interruption.
2. **SA Tenders** — scrape search results filtered by category/agency; parse contract notices into structured records
3. **Other states** — scrape on demand; not in initial pipeline

Contractor name matching uses normalised comparison (trimmed, lowercased), ABN-first. Unmatched names are written to `data/unmatched_suppliers_YYYY-MM-DD.csv` for review and potential addition to `entities.json`.

---

## Out of Scope

- Scheduling / automated runs (manual trigger only for now)
- ABN Lookup enrichment (deferred)
- Deduplication across entity aliases (same article linked to multiple entities is correct behaviour)
