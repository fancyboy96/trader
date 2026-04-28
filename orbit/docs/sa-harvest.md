# SA Government Contract Harvest

Approach and reference for `scripts/sa_harvest.py`.

## Overview

The SA harvester pulls contractor and consultant disclosure data published by South Australian government agencies to the [data.sa.gov.au](https://data.sa.gov.au) open data portal, and loads it into the local `orbit.db` SQLite database alongside the federal AusTender data.

Unlike the federal AusTender OCDS API (which provides a single unified JSON endpoint), SA government disclosure is fragmented — each agency publishes its own annual CSV or XLSX file as part of its annual report obligations under [PC-027 Disclosure of Government Contracts](https://www.dpc.sa.gov.au/resources-and-publications/premier-and-cabinet-circulars/PC-027-Disclosure-of-Government-Contracts.pdf).

---

## Data Source

**Portal:** `data.sa.gov.au` (CKAN)  
**API base:** `https://data.sa.gov.au/data/api/3/action`  
**Licence:** Creative Commons Attribution 4.0  
**Auth required:** None

The CKAN API supports tag-based and full-text dataset search, organisation browsing, and direct resource download. Results are paginated in sets of 100.

### Why not tenders.sa.gov.au?

The SA Tenders and Contracts portal (`tenders.sa.gov.au`) has a richer contracts register with dates, contract numbers, and buyer IDs — but it is protected by Cloudflare's JS challenge and serves server-side-rendered HTML with no XHR/Fetch API layer. Scraping it requires a real browser (Playwright) and is not yet implemented.

---

## CKAN Tag Strategy

Datasets are discovered by querying five exact tags. Tags are case-sensitive in CKAN's Solr backend:

| Tag | Datasets found |
|-----|---------------|
| `contractors` | ~21 |
| `consultants` | ~35 |
| `Consultants` | ~25 (distinct from lowercase) |
| `contractors engaged` | ~8 |
| `consultants engaged` | ~5 |

**Avoided tags:** `Contractors` (capital C) anomalously returns 120k+ results due to a Solr tokenisation quirk on this portal. Single-word stems (`contractor`, `consultant`, `consultancies`) similarly match 120k+. Free-text `q=` searches for these terms return 800+ noisy results.

Multi-word tags are quoted in the Solr `fq` parameter: `fq=tags:"contractors engaged"`.

---

## File Formats

Each CKAN dataset contains one or more resource files, typically one per financial year.

| Format | Handling |
|--------|----------|
| CSV | Downloaded and parsed with Python `csv` module. Uses `TextIOWrapper(newline='')` to correctly handle Windows line endings and quoted newlines. |
| XLSX | Downloaded and parsed with `openpyxl`. Requires `pip3 install openpyxl`. |
| XLS (legacy) | Skipped — requires `xlrd`. Rare on this portal. |

---

## Column Layout Variants

SA agencies do not use a standardised schema. The harvester detects and handles two layouts:

### Standard (most agencies)

```
name | purpose | value
```

Example — Defence SA:
```
Ai Group Centre for Education | Management of Defence Industry Scholarship Program | $12,000
```

### Inverted (ESCOSA, Housing Trust, Funds SA, PIRSA, State Opera…)

```
year | name [| purpose] | value
```

Example — ESCOSA:
```
2023-24 | Sapere Research Group Limited | Regulatory economic advice | $30,000
```

The harvester auto-detects inverted format by checking whether ≥50% of the first 15 non-empty first-column values match a year pattern (`YYYY-YY` or `YYYY/YY`). For inverted rows, the per-row year is also used as the FY date, which is more precise than the dataset/resource-level date.

---

## Financial Year Filtering

The default run imports the **last two complete financial years** (e.g. FY2023-24 and FY2024-25 as of April 2026). FY start year is inferred from:

1. Dataset title (e.g. `"Defence SA Contractors 2024-2025"` → FY2024)
2. Resource name/URL as fallback (e.g. `"DHS Annual Report Data 2023-24 - Contractors.csv"`)
3. Per-row year column for inverted-format datasets

Datasets and resources where the year cannot be determined are included (not filtered), since they may contain current-year data without an explicit year in the name.

---

## Data Quality Notes

- **No ABN:** SA disclosure data does not include ABNs. Entity matching is by name only, using `data/entities.json`.
- **No contract number:** Synthetic contract numbers are generated as `SA-CKAN-{md5hash}` from `(dataset_id, name, purpose, value)`. This makes reruns idempotent.
- **No dates for standard format:** Most standard-format CSV files don't include start/end dates. Dates are approximated from the financial year (July 1 → June 30).
- **Nil rows:** Some agencies (e.g. ESCOSA FY2023-24) report `Nil` for years with no engagements. These are correctly skipped.
- **Values in $000s (suspected):** Some small agencies (Lotteries Commission, PIRSA) appear to publish values in thousands rather than dollars. No correction is applied.
- **All contracts tagged `created_by = 'sa_ckan'`** for source traceability.

---

## Agencies Table

Each run populates the `agencies` reference table with org metadata fetched from the CKAN API:

```sql
SELECT name, slug, jurisdiction FROM agencies ORDER BY name;
```

34 SA government agencies are currently tracked.

---

## Usage

```bash
# Default: last 2 financial years
python3 scripts/sa_harvest.py

# Preview without writing to DB
python3 scripts/sa_harvest.py --dry-run

# All historical data
python3 scripts/sa_harvest.py --all-years

# Single agency (CKAN org slug)
python3 scripts/sa_harvest.py --org defence-sa

# From a specific FY start year
python3 scripts/sa_harvest.py --min-year 2022

# Single tag query
python3 scripts/sa_harvest.py --tag contractors
```

The script is **idempotent** — reruns skip already-ingested records via the synthetic contract number hash.

---

## Results (April 2026 baseline)

| Metric | Value |
|--------|-------|
| Datasets queried | 85 |
| Resources fetched (CSV + XLSX) | 137 |
| Resources skipped (year filter) | 150 |
| Contracts ingested | 1,203 |
| Agencies in reference table | 34 |
| Known entity matches | 25 |

Top agencies by contract count: South Australia Police (354), Department for Education (349), Defence SA (89), Department of the Premier and Cabinet (84).

---

## Known Gaps

| Gap | Cause | Fix |
|-----|-------|-----|
| tenders.sa.gov.au not harvested | Site bug (announced 10 Apr 2026) temporarily requires login for contract search; fix expected 17 Apr 2026 | Playwright scraper built (`scripts/sa_tenders_harvest.py`) — ready to run once bug resolved; credentials via `.env` as fallback |
| Legacy `.xls` files skipped | openpyxl can't read old Excel format | Add `xlrd` dependency |
| Infrastructure SA contractor XLSX empty | Agency published empty file for FY2024-25 | Upstream data issue |
| DIT contractors FY2023-24, FY2024-25 empty | Agency published empty CSVs | Upstream data issue |
| No ABN for entity matching | SA disclosure policy doesn't require ABN | Cross-reference via tenders.sa.gov.au when available |

---

## tenders.sa.gov.au — Planned Second Source

**Script:** `scripts/sa_tenders_harvest.py`  
**Status:** Built and tested; blocked by a temporary site bug until ~17 Apr 2026.

### What it is

The SA Tenders and Contracts portal (`tenders.sa.gov.au`) is the formal contract award register — agencies publish contract award notices here at time of award. This is distinct from the annual report disclosures on data.sa.gov.au (PC-027), which are retrospective aggregates.

### Why it's valuable

| Dimension | CKAN (data.sa.gov.au) | Tenders (tenders.sa.gov.au) |
|-----------|----------------------|------------------------------|
| Contracts (Apr 2026) | 2,370 | ~2,938 |
| Total disclosed value | $3.57B | Unknown (pending scrape) |
| Agencies covered | 20 | 63 |
| Date coverage | 55% (many undated) | ~100% (award date on every record) |
| Contract numbers | Synthetic (`SA-CKAN-{hash}`) | Real native numbers |
| ABNs | None | Likely present (formal notices) |
| Source | Annual report CSV/XLSX | Formal contract award notice |
| Scope | Contractors & consultants only | Broader — all procurement categories |

### Agency coverage gap

CKAN covers 20 agencies. tenders.sa.gov.au covers 63. Agencies in the tenders register but absent from CKAN include:

- Department for Child Protection (48 contracts)
- Department for Correctional Services (22)
- Department for Energy and Mining (41)
- Department for Environment and Water (33)
- Housing SA / Housing SA Asset Services (76 combined)
- Attorney Generals Department (58)
- Department for Housing and Urban Development (15)
- Courts Administration Authority (9)
- ForestrySA (9)
- 34 others (councils, boards, smaller agencies)

### DIT discrepancy

CKAN shows DIT with 634 contracts worth $3.24B; the tenders register shows 431. The CKAN data is likely higher because PC-027 disclosures capture sub-threshold engagements that don't require a formal tender notice. The two datasets are complementary, not redundant.

### Site access

The `buyerIndex` (`/contract/buyerIndex`) is fully public — no login required. Individual per-agency contract pages (`/contract/search?buyerId=X&browse=true`) normally require no login but are currently gated by a site bug. A permanent fix is targeted for 17 Apr 2026.

If credentials are needed before then, add to `.env`:
```
SA_TENDERS_EMAIL=you@example.com
SA_TENDERS_PASSWORD=yourpassword
```
Free Supplier accounts can be registered at `tenders.sa.gov.au/login → Sign Up`.

### Usage

```bash
# List all 63 agencies (public, no login needed — works now)
python3 scripts/sa_tenders_harvest.py --list-agencies

# Default run once site bug resolved (last 2 FYs)
python3 scripts/sa_tenders_harvest.py

# Dry run with visible browser to inspect scraped output
python3 scripts/sa_tenders_harvest.py --dry-run --headful

# Single agency
python3 scripts/sa_tenders_harvest.py --agency "Defence SA"

# Debug: save page HTML to data/debug/
python3 scripts/sa_tenders_harvest.py --save-html --max-pages 1
```
