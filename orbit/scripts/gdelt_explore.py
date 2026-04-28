#!/usr/bin/env python3
"""
GDELT query strategy explorer for Orbit Defence Intelligence.

Runs multiple query strategies against a set of test entities and prints
a comparison table so we can evaluate which approach yields the best results.
Does NOT write to the database — read-only exploration only.

Usage:
    python3 scripts/gdelt_explore.py
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMESPAN_DAYS = 30
MAX_RECORDS = 75


# ---------------------------------------------------------------------------
# Test entities — mix of businesses that got hits, ones that got zero,
# and programme-level queries
# ---------------------------------------------------------------------------

@dataclass
class TestEntity:
    label: str
    name: str
    aliases: list[str] = field(default_factory=list)
    context_terms: list[str] = field(default_factory=list)


TEST_ENTITIES = [
    # Got results — use as a baseline sanity check
    TestEntity("Boeing Defence Australia",   "Boeing Defence Australia",
               aliases=["Boeing Australia", "Boeing Defense Australia"]),

    # Got 0 — short/ambiguous name
    TestEntity("ASC Pty Ltd",               "ASC Pty Ltd",
               aliases=["Australian Submarine Corporation", "ASC"],
               context_terms=["submarine", "naval", "shipbuilding"]),

    # Got 0 — less prominent name in news
    TestEntity("Hanwha Defense Australia",  "Hanwha Defense Australia",
               aliases=["Hanwha Defence Australia", "Hanwha Defence", "Hanwha"],
               context_terms=["vehicle", "land", "LAND 400", "Redback", "Huntsman"]),

    # Got 0 — very short name, lots of noise risk
    TestEntity("NIOA",                      "NIOA",
               aliases=["NIOA Pty Ltd"],
               context_terms=["ammunition", "munitions", "weapons", "defence"]),

    # Programme-level — no specific business
    TestEntity("[Program] SSN-AUKUS",       "SSN-AUKUS",
               aliases=["AUKUS submarine", "nuclear submarine Australia", "SSN AUKUS"]),

    TestEntity("[Program] Hunter Frigate",  "Hunter class frigate",
               aliases=["SEA 5000", "Hunter frigate", "Type 26 frigate"]),
]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def build_name_clause(entity: TestEntity, include_aliases: bool) -> str:
    """Build the name portion of the query, optionally with aliases."""
    names = [f'"{entity.name}"']
    if include_aliases:
        names += [f'"{a}"' for a in entity.aliases]
    if len(names) == 1:
        return names[0]
    return "(" + " OR ".join(names) + ")"


STRATEGIES: list[tuple[str, callable]] = [
    (
        "1. Baseline (current)",
        lambda e: f'"{e.name}" defence Australia',
    ),
    (
        "2. + Aliases OR",
        lambda e: f'{build_name_clause(e, True)} defence Australia',
    ),
    (
        "3. + Aliases, no geo lock",
        lambda e: f'{build_name_clause(e, True)} (defence OR defense OR military OR contract)',
    ),
    (
        "4. + Aliases, English filter",
        lambda e: f'{build_name_clause(e, True)} (defence OR defense OR military) sourcelang:english',
    ),
    (
        "5. + Aliases, AU sources only",
        lambda e: f'{build_name_clause(e, True)} (defence OR defense OR military) sourcecountry:AU',
    ),
    (
        "6. Context terms only (no geo/lang)",
        lambda e: (
            f'{build_name_clause(e, True)} ({" OR ".join(e.context_terms)})'
            if e.context_terms
            else f'{build_name_clause(e, True)}'
        ),
    ),
]


# ---------------------------------------------------------------------------
# GDELT fetch
# ---------------------------------------------------------------------------

def fetch(query: str) -> list[dict]:
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(MAX_RECORDS),
        "timespan": f"{TIMESPAN_DAYS}d",
        "format": "json",
    }
    url = GDELT_BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "OrbitDefenceIntelligence/0.1"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                return data.get("articles") or []
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 15 * (attempt + 1)
                print(f" [rate limit, waiting {wait}s]", end="", flush=True)
                time.sleep(wait)
            else:
                print(f" [error: {e}]", end="", flush=True)
                return []
        except Exception as e:
            print(f" [error: {e}]", end="", flush=True)
            return []
    return []


def unique_domains(articles: list[dict]) -> list[str]:
    seen = []
    for a in articles:
        d = a.get("domain", "")
        if d and d not in seen:
            seen.append(d)
    return seen


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run():
    print(f"\nGDELT Strategy Explorer")
    print(f"Timespan : {TIMESPAN_DAYS} days   Max records : {MAX_RECORDS}")
    print("=" * 70)

    for entity in TEST_ENTITIES:
        print(f"\n{'─' * 70}")
        print(f"ENTITY: {entity.label}")
        print(f"{'─' * 70}")

        results: list[tuple[str, str, list[dict]]] = []

        for strategy_name, build_query in STRATEGIES:
            query = build_query(entity)
            print(f"  {strategy_name}", end="", flush=True)
            print(f"\n    Query: {query}")
            print(f"    Fetching ...", end="", flush=True)
            articles = fetch(query)
            print(f" {len(articles)} results")
            results.append((strategy_name, query, articles))
            time.sleep(5)

        # Summary table for this entity
        print(f"\n  Results summary:")
        print(f"  {'Strategy':<35} {'Count':>5}  {'Domains (sample)'}")
        print(f"  {'-'*35}  {'-'*5}  {'-'*30}")
        for name, _, articles in results:
            domains = ", ".join(unique_domains(articles)[:3])
            print(f"  {name:<35} {len(articles):>5}  {domains}")

        # Show headlines from best-performing strategy
        best_name, best_query, best_articles = max(results, key=lambda r: len(r[2]))
        if best_articles:
            print(f"\n  Best strategy: {best_name}")
            print(f"  Sample headlines:")
            for a in best_articles[:5]:
                print(f"    · {a.get('title', '(no title)')[:80]}")
                print(f"      {a.get('domain')}  {a.get('seendate', '')[:8]}")

    print(f"\n{'=' * 70}")
    print("Done.\n")


if __name__ == "__main__":
    run()
