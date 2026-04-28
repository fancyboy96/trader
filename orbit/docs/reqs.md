# Orbit Defence Intelligence — MVP Requirements

## Project Summary

Build the MVP of **Orbit Defence Intelligence**: a web application serving as a structured database of South Australian defence contracts and businesses, with automated news signal monitoring via GDELT. The MVP is intended for early subscriber access — paying users in the SA defence ecosystem who need a single, current, structured picture of who is active, what contracts exist, and what is happening in the market.

This is a production-grade application, not a prototype. It must be fast, reliable, and genuinely useful from day one.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript |
| Styling | Tailwind CSS |
| Database | Supabase (Postgres) |
| Auth | Supabase Auth (email/password + magic link) |
| File handling | Supabase Storage (CSV imports) |
| News signals | GDELT DOC 2.0 API (no key required) |
| AI extraction | Anthropic Claude API (claude-sonnet-4-20250514) |
| Deployment | Vercel |

---

## User Roles

| Role | Access |
|---|---|
| `admin` | Full read/write across all data, user management, CSV import, GDELT scan trigger |
| `subscriber` | Read-only access to all data; can save searches and set watchlists |

Authentication is required for all routes. No public-facing data.

---

## Data Models

### Business

```
id: uuid (PK)
name: string (required)
abn: string (optional, unique)
type: enum [prime_contractor, subcontractor, sme, government_agency, research_institution, other]
status: enum [active, inactive, watch]
description: text
website: string
address: string
suburb: string
state: string (default: SA)
employees_range: enum [1-10, 11-50, 51-200, 201-1000, 1000+]
capabilities: string[] (tags)
programs: string[] (canonical program slugs — see Appendix B)
asx_listed: boolean
created_at: timestamp
updated_at: timestamp
created_by: uuid (FK → user)
notes: text (admin only)
```

### Contract

```
id: uuid (PK)
title: string (required)
contract_number: string (optional)
status: enum [active, completed, pending, cancelled]
value_aud: bigint (nullable)
value_display: string (e.g. "$45B over 30 years" — for non-exact values)
awarded_date: date (nullable)
start_date: date (nullable)
end_date: date (nullable)
program: string (canonical program slug, e.g. "ssn-aukus" — see Appendix B for valid values)
category: enum [shipbuilding, land_systems, aviation, cyber, space, sustainment, professional_services, infrastructure, research, other]
prime_contractor_id: uuid (FK → Business)
contracting_agency: string (e.g. "Defence SA", "CASG", "DST Group")
source_url: string
description: text
notes: text (admin only)
created_at: timestamp
updated_at: timestamp
created_by: uuid (FK → user)
```

### ContractSubcontractor (junction table)

Replaces `subcontractors: uuid[]` on Contract. Enables efficient reverse lookups (all contracts a business appears on as a subcontractor).

```
contract_id: uuid (FK → Contract)
business_id: uuid (FK → Business)
PRIMARY KEY (contract_id, business_id)
```

### NewsSignal

```
id: uuid (PK)
headline: string
url: string (unique)
source_domain: string
published_at: timestamp
gdelt_tone: float (GDELT sentiment score)
summary: text (Claude-generated)
flags: string[] (e.g. ["contract_announcement", "leadership_change", "capability_signal"])
relevance_score: int (1–10, Claude-assessed)
scan_id: uuid (FK → GDELTScan)
created_at: timestamp
```

### NewsSignalBusiness (junction table)

Replaces `related_businesses: uuid[]` on NewsSignal. Enables efficient reverse lookups (all signals mentioning a business).

```
signal_id: uuid (FK → NewsSignal)
business_id: uuid (FK → Business)
PRIMARY KEY (signal_id, business_id)
```

### NewsSignalContract (junction table)

Replaces `related_contracts: uuid[]` on NewsSignal. Enables efficient reverse lookups (all signals mentioning a contract).

```
signal_id: uuid (FK → NewsSignal)
contract_id: uuid (FK → Contract)
PRIMARY KEY (signal_id, contract_id)
```

### GDELTScan

```
id: uuid (PK)
triggered_by: uuid (FK → user)
triggered_at: timestamp
entities_scanned: string[]
timespan_days: int
articles_found: int
signals_extracted: int
status: enum [running, complete, failed]
```

### WatchlistItem (subscriber feature)

```
id: uuid (PK)
user_id: uuid (FK → user)
entity_type: enum [business, contract, program]
entity_id: uuid
created_at: timestamp
```

---

## Application Pages & Features

### 1. Auth

- `/login` — email/password and magic link
- `/signup` — invite-only (admin creates invite links)
- Password reset flow

### 2. Dashboard (`/`)

Summary view for the signed-in user.

- **Stats bar:** Total businesses, active contracts, total contract value (summed), signals in last 7 days
- **Recent signals feed:** Last 10 GDELT news signals, sorted by relevance score descending, with headline, source, tone indicator, and linked entities
- **Watchlist activity:** Any new signals or data changes related to the user's watchlist items
- **Quick links:** Add business, Add contract, Run GDELT scan

### 3. Businesses (`/businesses`)

- Filterable, searchable table of all businesses
- Filters: type, status, state, capabilities (multi-select tags), program involvement
- Search: name, ABN, description full-text
- Columns: Name, Type, Status, Programs, Capabilities (truncated), Last signal date
- Click row → Business detail page
- Export current view as CSV (subscriber can export their filtered view)

**Business detail (`/businesses/[id]`)**

- Full business profile
- Linked contracts (as prime and as subcontractor)
- News signals mentioning this business (paginated)
- Watchlist toggle button
- Admin: edit, delete, add note

### 4. Contracts (`/contracts`)

- Filterable, searchable table of all contracts
- Filters: status, category, program, contracting agency, value range, date range
- Search: title, contract number, description full-text
- Columns: Title, Program, Status, Value, Prime Contractor, Awarded Date, Category
- Click row → Contract detail page

**Contract detail (`/contracts/[id]`)**

- Full contract profile
- Prime contractor card (linked to business)
- Subcontractor list (linked to businesses)
- News signals mentioning this contract
- Watchlist toggle button
- Admin: edit, delete, add note

### 5. News Signals (`/signals`)

- Feed of all GDELT-sourced signals, sorted by published date descending
- Filters: relevance score threshold, flags, date range, linked entity
- Each signal card shows: headline, source, published date, tone indicator (colour-coded), flags, Claude summary, linked businesses/contracts
- Click headline → opens source URL in new tab

### 6. Programs (`/programs`)

- Simple grouped view of all known defence programs
- Each program shows: description, total linked contract value, prime contractors, number of SA businesses involved
- Programs are not a separate data model — they are derived from the `program` field on contracts and businesses
- The canonical program slug list (see Appendix B) is the source of truth; the `program` field on Contract and Business must match a slug from this list. Free-text entry is not permitted — use a dropdown in all forms.
- No CRUD needed; this is a read-only derived view

### 7. Admin Panel (`/admin`)

Admin-only section.

#### 7a. Data Entry — Manual

- **Add Business** form: all fields from the Business model, capabilities as a tag input
- **Add Contract** form: all fields from the Contract model, prime/subcontractor linked via searchable business dropdown
- **Edit** and **soft-delete** for both entities

#### 7b. Data Entry — CSV Import

Two separate import flows: one for businesses, one for contracts.

**CSV Import flow:**
1. Download template CSV (pre-defined column headers matching the data model)
2. Upload populated CSV
3. Preview table showing parsed rows with validation errors highlighted
4. Confirm import — valid rows inserted, invalid rows shown with error reason
5. Import summary shown on completion

**Business CSV columns:**
`name, abn, type, status, description, website, address, suburb, state, employees_range, capabilities (semicolon-separated), asx_listed`

**Contract CSV columns:**
`title, contract_number, status, value_aud, value_display, awarded_date, start_date, end_date, program, category, prime_contractor_name, subcontractor_names (semicolon-separated), contracting_agency, source_url, description`

For CSV imports, `prime_contractor_name` and `subcontractor_names` are matched against existing businesses by name (case-insensitive). Matching is done against a normalised name (trimmed, lowercased) to reduce false negatives, but partial matching is not performed — "BAE Systems" will not match "BAE Systems Australia". Unmatched names are flagged as warnings but do not block import — they are stored as plain text in an `unlinked_parties` field and can be resolved later via the admin UI.

#### 7c. GDELT Scan

- Select entities to scan (multi-select from business list, or scan all)
- Select timespan: 7 days, 14 days, 30 days
- Trigger scan button
- Progress indicator while scan runs (server-sent events or polling)
- On completion: summary of articles found, signals extracted, new businesses/contracts auto-detected

**GDELT scan logic (backend):**
1. For each selected business, query GDELT DOC 2.0 API: `https://api.gdeltproject.org/api/v2/doc/doc?query={business_name} defence Australia&mode=artlist&maxrecords=25&timespan={days}d&format=json`
2. Deduplicate articles by URL against existing NewsSignals
3. For each new article, send headline + snippet to Claude with structured extraction prompt (see Appendix A)
4. Store extracted NewsSignal records
5. Update GDELTScan record on completion

> **Implementation note:** Scanning all businesses can take several minutes and will exceed Vercel's 60s serverless function timeout. The scan must be implemented as a Supabase Edge Function (or equivalent background worker) invoked asynchronously. The Next.js API route (`POST /api/scan/gdelt`) creates the GDELTScan record and triggers the background function, then returns immediately. The frontend polls `GET /api/scan/[id]/status` for progress.

#### 7d. User Management

- List of all users with role and last login
- Create invite link (sets role on signup)
- Change user role
- Deactivate user

---

## Search

Global search bar in the nav (cmd+K) searches across businesses and contracts simultaneously. Results grouped by type. Implemented using Postgres full-text search via Supabase.

---

## UI/UX Requirements

### Visual Direction

Modern Bloomberg Terminal aesthetic — information-dense, professional, and data-forward — but implemented as a proper GUI (not a text-mode replica). Reference points: Bloomberg Terminal's density and colour language, but with modern typography, hover states, smooth transitions, and interactive components.

**Colour palette:**
- Background: near-black (not pure black — something like `#0a0a0f` or `#0d1117`)
- Surface/card: very dark grey (`#13151a` range)
- Borders: subtle, low-contrast (`#1e2028` range)
- Primary accent: amber/orange (`#f59e0b` or similar) — Bloomberg's signature colour; used sparingly for key figures, active states, and highlights
- Secondary accent: muted teal or steel blue for secondary actions and links
- Text primary: off-white (`#e2e8f0`)
- Text secondary: medium grey (`#64748b`)
- Positive values: green (`#22c55e`)
- Negative/warning values: red (`#ef4444`)

**Typography:**
- Monospace or semi-monospace for data values, contract amounts, dates, and IDs — reinforces the terminal feel
- Clean sans-serif (e.g. Inter) for labels, headings, and body copy
- Tight line heights and compact spacing throughout

**Component style:**
- Tables are the primary data display — dense rows, minimal padding, sortable columns
- Data cards use a dark surface with a subtle border, no drop shadows
- Stat figures are large and bold with a label in small caps beneath
- Colour-coded badges for status fields (active/inactive/watch, contract status, signal flags)
- Tone indicators on news signals use a colour bar or dot (green → red spectrum matching GDELT tone score)

### General UX

- Responsive but desktop-first. Users will primarily access via desktop browser.
- Loading states on all async operations.
- Toast notifications for all create/update/delete actions.
- Confirm dialog before any delete action.
- Empty states with clear calls to action on all list views.

---

## API Routes (Next.js Route Handlers)

```
GET    /api/businesses          — list with filters
POST   /api/businesses          — create (admin)
GET    /api/businesses/[id]     — detail
PUT    /api/businesses/[id]     — update (admin)
DELETE /api/businesses/[id]     — soft delete (admin)

GET    /api/contracts           — list with filters
POST   /api/contracts           — create (admin)
GET    /api/contracts/[id]      — detail
PUT    /api/contracts/[id]      — update (admin)
DELETE /api/contracts/[id]      — soft delete (admin)

GET    /api/signals             — list with filters
GET    /api/signals/[id]        — detail

POST   /api/import/businesses   — CSV import (admin)
POST   /api/import/contracts    — CSV import (admin)

POST   /api/scan/gdelt          — trigger GDELT scan (admin)
GET    /api/scan/[id]/status    — poll scan status

GET    /api/watchlist           — user's watchlist
POST   /api/watchlist           — add item
DELETE /api/watchlist/[id]      — remove item

GET    /api/admin/users         — list users (admin)
POST   /api/admin/invite        — create invite (admin)
PUT    /api/admin/users/[id]    — update role/status (admin)
```

---

## Appendix A — Claude Extraction Prompt (GDELT Signal Processing)

Used in the GDELT scan pipeline. Send as a system prompt with the article headline and snippet as user content.

```
You are an intelligence analyst specialising in the Australian defence industry, 
with a focus on South Australia.

Analyse the following news article and extract structured intelligence relevant 
to the SA defence ecosystem.

Respond ONLY with a valid JSON object in this exact format:

{
  "summary": "2-3 sentence plain English summary of the article",
  "relevance_score": <integer 1-10, where 10 = directly about SA defence contracts/companies>,
  "flags": [<array of strings from: contract_announcement, capability_signal, leadership_change, program_update, industry_event, export_opportunity, supply_chain_signal, regulatory_change, funding_announcement, other>],
  "mentioned_businesses": [<array of company names mentioned>],
  "mentioned_programs": [<array of defence program names mentioned, e.g. "SSN-AUKUS", "LAND 400">],
  "contract_value_mentioned": <string or null, e.g. "$2.4B">,
  "key_insight": "One sentence — the single most actionable intelligence takeaway from this article"
}

If the article has no relevance to Australian or SA defence, set relevance_score to 1 
and return empty arrays for flags and mentions.
```

---

## Appendix B — Seed Data

Populate on first deploy with the following SA defence entities (businesses) and programs so the application is not empty:

**Businesses (primes):**
- BAE Systems Australia
- Hanwha Defense Australia
- ASC Pty Ltd
- Thales Australia
- Saab Australia
- Boeing Defence Australia
- Lockheed Martin Australia
- Raytheon Australia
- L3Harris Australia
- NIOA

**Programs (canonical slugs and display names):**

| Slug | Display Name |
|---|---|
| `ssn-aukus` | SSN-AUKUS |
| `sea-5000` | Hunter Class Frigates (SEA 5000) |
| `land-400-phase-3` | LAND 400 Phase 3 |
| `land-8116` | LAND 8116 (AS9 Huntsman / AS21 Redback) |
| `air-6500` | AIR 6500 |
| `defence-sa-industry` | Defence SA Industry Programs |

The `program` field on Contract and Business stores the slug. The UI always renders the display name. New programs can be added to this list by an admin — adding a new entry here is the only way to introduce a new program slug into the system.

---

## Data Pipeline Conventions

Rules that apply to all harvest scripts (`scripts/austender_harvest.py`, `scripts/sa_harvest.py`, and any future state/territory scrapers):

### Contractor upsert on every run

Every harvester **must** upsert contractors into the `businesses` table as it ingests contracts. Do not defer business creation to a separate step.

- Use `upsert_business()` — check by ABN first (if available), fall back to exact name match, then insert if not found.
- On insert, always set `created_by` to the source tag for that harvester (e.g. `'austender'`, `'sa_ckan'`).
- If a business already exists (matched by ABN or name), do not overwrite — just return the existing `id`. The harvester's job is discovery, not curation.

### Source tags (`created_by`)

| Value | Source |
|-------|--------|
| `austender` | Federal AusTender OCDS API |
| `sa_ckan` | SA Government data.sa.gov.au (CKAN) |
| *(future)* `tenders_sa` | tenders.sa.gov.au (Playwright scraper) |
| *(future)* `wa_tenders` | WA Government tenders portal |
| `manual` | Admin UI / CSV import |

The same `created_by` convention applies to both the `businesses` and `contracts` tables.

### No ABN for SA CKAN

SA government disclosure data does not include ABNs. SA CKAN businesses are matched by name only — this means name variants (e.g. "Randstad Pty Ltd" vs "Randstad Pty Limited") will create separate records. Deduplication via ABN lookup is a post-MVP task.

---

## Out of Scope for MVP

The following are explicitly deferred to post-MVP:

- Public-facing marketing site
- Automated nightly GDELT scans (MVP: manual trigger only)
- Email digest / notifications
- API access for subscribers
- Mobile app
- Payment / subscription billing integration
- Map visualisation of SA defence businesses
- Relationship graph view (who works with whom)
- Document/tender upload and parsing

