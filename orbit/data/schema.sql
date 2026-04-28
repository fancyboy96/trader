-- Orbit Defence Intelligence — SQLite Schema
-- Mirrors the Postgres/Supabase schema defined in docs/reqs.md
-- Used for local data harvesting prior to Supabase setup.
-- Arrays (capabilities, flags, etc.) are stored as JSON text.

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Businesses
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS businesses (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  abn               TEXT UNIQUE,
  type              TEXT CHECK(type IN ('prime_contractor','subcontractor','sme','government_agency','research_institution','other')),
  status            TEXT CHECK(status IN ('active','inactive','watch')) DEFAULT 'active',
  description       TEXT,
  website           TEXT,
  address           TEXT,
  suburb            TEXT,
  state             TEXT DEFAULT 'SA',
  employees_range   TEXT CHECK(employees_range IN ('1-10','11-50','51-200','201-1000','1000+')),
  capabilities      TEXT DEFAULT '[]',  -- JSON array of strings
  programs          TEXT DEFAULT '[]',  -- JSON array of canonical slugs
  asx_listed        INTEGER DEFAULT 0,  -- 0 = false, 1 = true
  asx_ticker        TEXT,               -- ASX ticker code, e.g. 'CDA'
  notes             TEXT,
  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now')),
  created_by        TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_businesses_asx_ticker
  ON businesses(asx_ticker) WHERE asx_ticker IS NOT NULL;

-- ------------------------------------------------------------
-- Contracts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contracts (
  id                  TEXT PRIMARY KEY,
  title               TEXT NOT NULL,
  contract_number     TEXT,
  status              TEXT CHECK(status IN ('active','completed','pending','cancelled')) DEFAULT 'active',
  value_aud           INTEGER,
  value_display       TEXT,
  awarded_date        TEXT,
  start_date          TEXT,
  end_date            TEXT,
  program             TEXT,  -- canonical program slug
  category            TEXT CHECK(category IN ('shipbuilding','land_systems','aviation','cyber','space','sustainment','professional_services','infrastructure','research','other')),
  prime_contractor_id TEXT REFERENCES businesses(id),
  contracting_agency  TEXT,
  procurement_method  TEXT,  -- open, limited, direct
  unspsc_code         TEXT,  -- UNSPSC category code from OCDS
  description         TEXT,
  unlinked_parties    TEXT DEFAULT '[]',  -- JSON array: contractor names that couldn't be matched
  notes               TEXT,
  created_at          TEXT DEFAULT (datetime('now')),
  updated_at          TEXT DEFAULT (datetime('now')),
  created_by          TEXT
);

-- ------------------------------------------------------------
-- Contract ↔ Subcontractor junction
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contract_subcontractors (
  contract_id   TEXT NOT NULL REFERENCES contracts(id),
  business_id   TEXT NOT NULL REFERENCES businesses(id),
  PRIMARY KEY (contract_id, business_id)
);

-- ------------------------------------------------------------
-- Agencies (SA government reference table)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agencies (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  slug         TEXT UNIQUE,        -- CKAN organisation slug
  state        TEXT DEFAULT 'SA',
  jurisdiction TEXT,               -- e.g. 'Government of South Australia'
  website      TEXT,
  notes        TEXT,
  created_at   TEXT DEFAULT (datetime('now')),
  updated_at   TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- Business Relationships
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS business_relationships (
  id               TEXT PRIMARY KEY,
  from_business_id TEXT NOT NULL REFERENCES businesses(id),
  to_business_id   TEXT NOT NULL REFERENCES businesses(id),
  relationship     TEXT CHECK(relationship IN (
    'parent', 'subsidiary', 'jv_partner', 'historically_associated'
  )),
  effective_from   TEXT,  -- ISO date, optional
  effective_to     TEXT,  -- ISO date, optional
  notes            TEXT
);

-- ------------------------------------------------------------
-- GDELT Scans
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gdelt_scans (
  id                TEXT PRIMARY KEY,
  triggered_by      TEXT,
  triggered_at      TEXT DEFAULT (datetime('now')),
  entities_scanned  TEXT DEFAULT '[]',  -- JSON array of business names
  timespan_days     INTEGER,
  articles_found    INTEGER DEFAULT 0,
  signals_extracted INTEGER DEFAULT 0,
  status            TEXT CHECK(status IN ('running','complete','failed')) DEFAULT 'running'
);

-- ------------------------------------------------------------
-- News Signals
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_signals (
  id               TEXT PRIMARY KEY,
  headline         TEXT,
  url              TEXT UNIQUE,
  source_domain    TEXT,
  published_at     TEXT,
  gdelt_tone       REAL,
  summary          TEXT,
  flags            TEXT DEFAULT '[]',  -- JSON array of flag strings
  relevance_score  INTEGER,
  scan_id          TEXT REFERENCES gdelt_scans(id),
  -- Claude extras stored from extraction prompt
  mentioned_programs    TEXT DEFAULT '[]',  -- JSON array
  contract_value_mentioned TEXT,
  key_insight      TEXT,
  created_at       TEXT DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- NewsSignal ↔ Business junction
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_signal_businesses (
  signal_id    TEXT NOT NULL REFERENCES news_signals(id),
  business_id  TEXT NOT NULL REFERENCES businesses(id),
  PRIMARY KEY (signal_id, business_id)
);

-- ------------------------------------------------------------
-- NewsSignal ↔ Contract junction
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_signal_contracts (
  signal_id    TEXT NOT NULL REFERENCES news_signals(id),
  contract_id  TEXT NOT NULL REFERENCES contracts(id),
  PRIMARY KEY (signal_id, contract_id)
);
