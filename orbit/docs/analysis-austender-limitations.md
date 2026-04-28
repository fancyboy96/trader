# AusTender Data — Limitations & Analysis

## Data Coverage

- **Source:** AusTender OCDS API (`api.tenders.gov.au/ocds`)
- **Period:** July 2023 – April 2026 (~3-year harvest, full FY2024–FY2026)
- **Scope:** All Commonwealth agencies (not defence-only)
- **Total contracts:** 162,108
- **Total contract value:** $180.3B
- **Unique contractors:** 28,262

---

## Limitations

### 1. 77% of contracts are limited tender — no competitive visibility

| Method | Contracts | Value |
|---|---|---|
| Limited tender | 43,365 (77%) | $44.3B |
| Open tender | 12,696 (23%) | $31.2B |

Limited tender means the agency went direct to a single supplier without open competition. AusTender records who won but provides no visibility into evaluation criteria, whether other suppliers were considered, or what alternatives existed. The majority of defence procurement by contract count happens outside a competitive process.

### 2. Pass-through accounts distort supplier spend

Several high-value "suppliers" are not real companies — they are financial channels for foreign government-to-government procurement:

| Name | Contracts | Value |
|---|---|---|
| FMS Account Reserve Bank of Australia | 94 | $9.3B |
| ACEA Cooperative Program | 1 | $261M |
| NGJ Cooperative Program | 2 | $31.8M |
| ALWT Armaments Cooperative Program | 1 | $20.3M |
| Federal Reserve Bank of NY – ITS | 9 | $32M |

The FMS (Foreign Military Sales) account is the US Government-to-Government channel — Australian purchases of US-origin weapons (missiles, aircraft systems, etc.) are routed through the Reserve Bank rather than paid directly to the US manufacturer. These entries should be excluded from supplier analysis and treated as a separate category.

Total pass-through / non-supplier value: ~**$9.6B** (13% of total dataset value).

### 3. No subcontractor data

AusTender records only the prime awardee per contract notice. A $500M systems integration contract may involve dozens of subcontractors — none of whom appear in this dataset. Subcontractor relationships require a separate source (e.g. company annual reports, industry registers, or direct disclosure).

### 4. Value distribution — 65% of contracts are under $80k

| Value band | Contracts | % |
|---|---|---|
| $10k – $80k | 36,163 | 65% |
| $80k – $500k | 13,350 | 24% |
| $500k – $5M | 5,581 | 10% |
| $5M – $50M | 885 | 2% |
| Over $50M | 147 | 0.3% |

$80k is the Commonwealth limited tender threshold — below it, agencies can procure direct with minimal process. The dataset has significant routine procurement noise (consumables, small IT purchases, catering, vehicle parts) mixed with strategically significant contracts. Filtering to contracts above $500k–$1M gives a cleaner strategic picture.

### 5. Contract amendments not tracked

When a contract is amended (value increased, term extended), AusTender may publish a new or amended notice. The OCDS data does not reliably link amendments back to original contracts — so a contract that grew from $10M to $50M may appear as separate records or its history may be incomplete.

### 6. Single-agency view — state contracts absent

This dataset covers Commonwealth agencies only. State government defence procurement (Defence SA, state police, emergency services) is entirely separate and requires scraping individual state tender portals (`tenders.sa.gov.au`, etc.).

### 7. No contract description detail

Contract titles in AusTender are often generic ("Support Services", "ICT Services", "Labour Support Services") with no further description of scope. There is insufficient detail to determine what was actually procured from the title alone.

### 8. PwC and Cognizant absence

PricewaterhouseCoopers and Cognizant do not appear in the dataset under any name variant. Possible explanations:
- PwC's government consulting arm was spun out as **Scyne Advisory** in 2023 following the tax scandal — Scyne appears separately with $30.7M in contracts
- Cognizant may operate through subcontracting arrangements not visible in AusTender
- Both may have Commonwealth work that falls below reporting thresholds or through panel arrangements reported differently

---

## Consulting & Advisory Firm Spend (2024–2026)

All-of-government spend across all Commonwealth agencies. Matched by firm name variants in supplier records.

> **Note on EY matching**: The pattern `%EY%` is too broad and catches unrelated suppliers (e.g. "SECURE JOURNEYS PTY LTD", $4.7B). EY figures use `LIKE "Ernst%Young%"` plus known EY subsidiary names.
> **Note on BCG**: Boston Consulting Group appears under "BOSTON CONSULTING GROUP" — BCG's $99M is dominated by a single DFAT Australian Aid Program contract, which inflates their headline number relative to defence/domestic work.

| Firm | Total Value | Contracts | Top Client Agency |
|---|---|---|---|
| Accenture | $1,009M | 112 | Health ($322M), ATO ($216M), Defence ($184M) |
| IBM | $468M | 93 | Home Affairs ($179M), Defence ($162M), Services Australia ($72M) |
| EY | $323M | 288 | Defence ($105M), AEC ($27M), ATO ($24M) |
| Deloitte | $306M | 370 | Defence ($142M), Education ($17M), Health ($17M) |
| KPMG | $220M | 532 | Defence ($80M), Finance ($15M), Home Affairs ($10M) |
| BCG | $126M | 24 | DFAT Aid ($99M single contract), Defence ($11M) |
| Scyne Advisory | $92M | 100 | Defence ($31M), Health ($19M) — formerly PwC govt arm |
| Capgemini | $66M | 34 | Defence ($25M), NDIS ($14M), Health ($10M) |
| Gartner | $40M | 128 | Defence ($13M), Home Affairs ($3M) |
| McKinsey | $26M | 27 | Defence ($11M), Submarine Agency ($10M) |
| PwC | $11M | 9 | ANAO ($11M) — residual post-rebrand contracts |
| Bain | $0.4M | 10 | DVA ($0.2M), ODPP ($0.2M) |
| Cognizant | $0.05M | 1 | AFSA — essentially absent from dataset |
| **Total** | **$2.69B** | **1,728** | |

### By Financial Year

> **FY2026 is partial** — data runs to April 2026 (Q3 of FY2026 only).

| Firm | FY2024 | FY2025 | FY2026* | Total |
|---|---|---|---|---|
| Accenture | $218M (66) | $622M (43) | $236M (36) | $1,076M |
| IBM | $346M (48) | $265M (40) | $144M (28) | $755M |
| Deloitte | $152M (202) | $166M (190) | $91M (84) | $409M |
| KPMG | $231M (350) | $111M (233) | $61M (140) | $403M |
| EY | $142M (162) | $156M (134) | $74M (59) | $372M |
| BCG | $6M (7) | $115M (12) | $7M (8) | $128M |
| Scyne Advisory | $21M (25) | $57M (47) | $17M (32) | $95M |
| Capgemini | $7M (16) | $32M (16) | $27M (9) | $67M |
| Gartner | $24M (67) | $18M (59) | $7M (27) | $49M |
| McKinsey | $10M (9) | $16M (16) | $4M (8) | $30M |
| PwC | $11M (6) | $0.2M (5) | $0M (1) | $12M |
| Bain | $0.1M (2) | $0.2M (4) | $0.2M (6) | $0.4M |
| Cognizant | $0.05M (1) | — | — | $0.05M |
| **Total** | **$1,169M (961)** | **$1,558M (799)** | **$669M (438)** | **$3,397M** |

*Numbers in brackets = contract count. \* FY2026 partial to April 2026.*

**IBM FY2024 spike:** IBM's $346M in FY2024 vs $265M in FY2025 suggests large multi-year contracts awarded in H1 FY2024 (Jul–Dec 2023) — likely Department of Home Affairs identity/border systems and Defence IT infrastructure.
**KPMG FY2024:** Similarly elevated at $231M vs $111M in FY2025, reflecting large engagements awarded early in the period.
**BCG FY2025 spike:** $115M vs $6M in FY2024 — almost entirely one $99M DFAT Australian Aid Program contract.

### Key observations

- **$2.7B** went to consulting and advisory firms across 1,728 contracts in 2 years (all Commonwealth agencies)
- **Accenture leads by a large margin** ($1.009B, 112 contracts) — average contract $9M — largest single client is Health, not Defence
- **KPMG leads on volume** (532 contracts) — small average engagement ($414k), broadest agency spread
- **EY's Defence contracts** ($105M) include large single-agency engagements; EY is present across 30+ agencies
- **IBM's Home Affairs spend** ($179M) is their largest client — likely identity/border systems
- **BCG's $99M** is a single DFAT Australian Aid Program contract — remove that and BCG's total falls to $27M
- **Scyne Advisory** (formerly PwC government arm, rebranded Oct 2023) has $92M — PwC appears with only $11M in residual pre-rebrand work
- **MBB overall**: McKinsey $26M, BCG $126M (mostly one anomalous DFAT contract), Bain $0.4M
- **Cognizant** has one contract worth $50k — almost certainly operates as a subcontractor to primes, invisible in AusTender
- Contract titles are uniformly vague — "Support Services", "Capability Development Services" — impossible to assess actual scope from title alone

---

## Recommended Filters for Meaningful Analysis

To cut through procurement noise and focus on strategically significant contracts:

```sql
-- Contracts worth analysing
WHERE value_aud >= 1000000          -- over $1M
  AND procurement_method = 'open'   -- competitively tendered
  AND contracting_agency NOT LIKE '%Reserve Bank%'  -- exclude pass-throughs
```

For supplier analysis, exclude pass-through accounts:
```sql
WHERE b.name NOT LIKE '%FMS ACCOUNT%'
  AND b.name NOT LIKE '%COOPERATIVE PROGRAM%'
  AND b.name NOT LIKE '%RESERVE BANK%'
  AND b.name NOT LIKE '%FEDERAL RESERVE%'
```
