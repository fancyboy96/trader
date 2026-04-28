# Orbit — Todo

## Done

### Data Pipeline
- [x] Defined SQLite schema mirroring the Postgres/Supabase data model (`data/schema.sql`)
- [x] Built GDELT scan script (`scripts/gdelt_scan.py`) — queries GDELT DOC 2.0 API, deduplicates by URL, stores raw signals in SQLite
- [x] Explored GDELT query strategies — tested 6 approaches across 6 entities; confirmed Strategy 3 (aliases OR + broad context terms, no geo lock) as optimal
- [x] Built AusTender OCDS harvester (`scripts/austender_harvest.py`) — paginates full government contract feed, filters for defence agencies, matches suppliers against entity list, stores businesses and contracts in SQLite
- [x] Defined entity config (`data/entities.json`) — canonical names, aliases, and context terms for 12 seed businesses and 4 programs
- [x] Added TKMS Sonartech Atlas and Aero Defence to entity config based on AusTender harvest results
- [x] Fixed duplicate ABN constraint — `upsert_business` now checks by ABN before name
- [x] Added `procurement_method` and `unspsc_code` to contracts schema and harvester
- [x] First real GDELT scan — 8 signals stored including Ghost Bat/MQ-28 Germany deal and Raytheon/BAE coverage
- [x] Full 2-year AusTender harvest (all Commonwealth agencies, no defence filter) — 131,938 contracts, 25,324 unique contractors, $141.2B total value
- [x] Built export analysis script (`scripts/export_analysis.py`) — produces contracts CSV and contractors CSV with year-by-year value breakdown
- [x] Unmatched suppliers written to CSV after each harvest run (with ABN) for manual entity review
- [x] Consulting/Big4/MBB spend analysis across all agencies — $2.69B across 1,728 contracts; corrected EY matching (avoid `%EY%` — too broad)
- [x] SA CKAN harvester (`scripts/sa_harvest.py`) — pulls contractor/consultant disclosure CSVs and XLSX from data.sa.gov.au, inserts into `businesses` and `contracts` tables. April 2026 baseline: 1,203 contracts, 808 contractors, $241M, 34 agencies
- [x] All harvesters upsert contractors to `businesses` table on every run — `created_by` set to source tag (`austender`, `sa_ckan`) for traceability

### Docs & Specs
- [x] `docs/reqs.md` — full MVP application requirements including data models, pages, API routes, UI direction
- [x] `docs/reqs-extraction.md` — extraction pipeline spec covering entity setup (Part 1), GDELT query strategy (Part 2), and contract data sources (Part 3)
- [x] Applied spec improvements: junction tables, canonical program slugs, CSV name matching, GDELT/Vercel timeout note, Bloomberg Terminal UI direction
- [x] `docs/todo.md` — this file

---

## Up Next

### Contractor Enrichment Pipeline (see `docs/contractor-enrichment.md`)
- [ ] Phase 1: Build `scripts/abn_enrichment.py` — ABN Lookup API for all ~24k contractors with ABNs; fills state, entity type, clean legal name
- [ ] Phase 2: Build `scripts/contractor_gdelt_scan.py` — GDELT sweep for Tier 1 (>$10M, ~1,600) and Tier 2 ($1M–$10M, ~4,200) contractors
- [ ] Phase 3: Claude extraction pass over raw GDELT signals + contractor profile generation — blocked on Anthropic API key
- [ ] Add `enrichment_runs` table to schema for checkpoint/audit tracking

### Data Pipeline — Immediate
- [ ] Review `data/unmatched_suppliers_*.csv` — identify further suppliers for `entities.json` (Rheinmetall MAN, Milspec, Anduril, CEA Technologies are candidates)
- [ ] Update `gdelt_scan.py` to read from `entities.json` instead of hardcoded seed list
- [ ] Update `gdelt_scan.py` to use Strategy 3 query construction
- [ ] Add Claude extraction to GDELT scan (relevance scoring, flags, summary, key insight) — blocked on Anthropic API key

### Data Pipeline — Soon
- [ ] Incremental AusTender runs — 2-year historical pull done; set up weekly `--from <last-run-date>` runs
- [x] SA Tenders scraper (`scripts/sa_tenders_harvest.py`) — Playwright browser scraper built; public `buyerIndex` confirmed (63 agencies, ~3,500+ contracts); per-agency contract pages temporarily require login due to a site bug (expected fix 17 Apr 2026); credentials supported via `.env` SA_TENDERS_EMAIL / SA_TENDERS_PASSWORD
- [ ] State tender scrapers (WA, NSW, VIC, QLD) — secondary priority
- [ ] ABN-based deduplication for SA contractors — SA CKAN has no ABN; cross-reference via tenders.sa.gov.au or ABN Lookup when available

### Application — MVP Build
- [ ] Scaffold Next.js 14 app (App Router + TypeScript + Tailwind)
- [ ] Set up Supabase project — schema migration from `data/schema.sql`
- [ ] Write SQLite → Supabase seed script to import harvested data
- [ ] Implement auth (Supabase Auth — email/password + magic link, invite-only signup)
- [ ] Dashboard page — stats bar, recent signals feed, watchlist activity
- [ ] Businesses list + detail pages
- [ ] Contracts list + detail pages
- [ ] News signals feed
- [ ] Programs derived view
- [ ] Admin panel — manual data entry, CSV import, GDELT scan trigger, user management
- [ ] Global search (cmd+K, Postgres full-text)
- [ ] Wire GDELT scan pipeline into app API route (`POST /api/scan/gdelt` → Supabase Edge Function)

### Open Questions
- [ ] Anthropic API key — needed to activate Claude extraction layer
- [ ] Supabase project — when to set up and start building against real DB
