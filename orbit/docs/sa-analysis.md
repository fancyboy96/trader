# SA Government Contractor Disclosure — Initial Analysis

**Data source:** data.sa.gov.au (CKAN), harvested April 2026  
**Coverage:** FY2023-24 and FY2024-25 (where dated); SAPOL and some agencies have no date on records  
**Script:** `scripts/sa_harvest.py`  

---

## Overview

| Metric | Value |
|--------|-------|
| Total contracts | 1,203 |
| Unique contractors | 808 |
| Total disclosed value | $241.3M |
| Average contract value | $200,578 |
| Median contract value | $41,300 |
| Largest single contract | $7.67M |

The median/mean gap ($41K vs $200K) reflects a long tail — a small number of large labour hire arrangements account for the majority of spend.

---

## By Agency

| Agency | Contracts | Total ($M) | Avg ($) |
|--------|-----------|-----------|---------|
| South Australia Police | 354 | $143.4M | $405,181 |
| Department for Education | 349 | $64.0M | $183,329 |
| Department of Human Services | 95 | $8.5M | $89,038 |
| Department of the Premier and Cabinet | 84 | $7.8M | $92,446 |
| Department of State Development | 103 | $5.7M | $55,381 |
| SA Health | 27 | $4.9M | $181,139 |
| Defence SA | 89 | $2.9M | $32,951 |
| History Trust of South Australia | 28 | $1.8M | $63,010 |
| South Australian Film Corporation | 47 | $1.4M | $28,704 |
| ESCOSA | 9 | $0.6M | $68,767 |

**SAPOL and Education together account for $207M (86%) of total disclosed spend.** SAPOL's outsized share reflects large, multi-year agency staff arrangements for administrative, ICT, and COVID support functions.

---

## By Category (estimated)

| Category | Contracts | Total ($M) | Share |
|----------|-----------|-----------|-------|
| Labour Hire / Recruitment | 226 | $144.5M | 60% |
| Other Professional Services | 827 | $74.3M | 31% |
| Security Services | 26 | $10.0M | 4% |
| ICT / Technology | 49 | $7.0M | 3% |
| Management Consulting | 75 | $5.6M | 2% |

Categories are estimated via contractor name and contract title matching — not a formal taxonomy. Labour hire dominates, largely driven by SAPOL's use of Hays, Randstad, Paxus, and Akkodis for administrative and IS&T agency staff.

---

## Top 20 Contractors by Value

| Contractor | Contracts | Total ($M) |
|-----------|-----------|-----------|
| Hays Specialist Recruitment | 12 | $23.7M |
| Randstad Pty Ltd | 6 | $18.7M |
| Paxus Australia Pty Ltd | 7 | $15.6M |
| Dialog Pty Ltd | 6 | $9.6M |
| Akkodis Australia Talent | 5 | $7.1M |
| Schools Ministry Group | 1 | $5.7M |
| Innodev Pty Ltd | 3 | $5.7M |
| Peoplebank Australia Ltd | 8 | $5.6M |
| Escient Pty Ltd | 7 | $5.5M |
| Randstad Pty Limited | 1 | $5.0M |
| Hoban Recruitment Pty Ltd | 4 | $4.9M |
| DFP Recruitment Services | 7 | $3.9M |
| Edge Recruitment | 7 | $3.6M |
| State Security & Protective Services | 5 | $3.4M |
| Access Testing Pty Ltd | 5 | $3.3M |
| Talent International (SA) | 8 | $3.2M |
| Fragile To Agile (Asia Pac) | 3 | $3.1M |
| AG Security Group | 4 | $3.0M |
| Total Contractors *(SA Health aggregate)* | 1 | $2.5M |
| NRI Australia Limited | 3 | $2.2M |

Note: Randstad appears twice as "Randstad Pty Ltd" and "Randstad Pty Limited" — combined total ~$23.7M, roughly matching Hays. These are likely the same entity under different registered names.

---

## Notable Contracts Over $1M

| Contractor | Description | Agency | Value |
|-----------|-------------|--------|-------|
| Hays Specialist Recruitment | Labour resources | Dept for Education | $7.67M |
| Randstad Pty Ltd | Admin/COVID agency staff | SA Police | $6.43M |
| Paxus Australia | IS&T agency staff | SA Police | $5.68M |
| Schools Ministry Group | National Student Wellbeing Program | Dept for Education | $5.68M |
| Paxus Australia | IS&T agency staff (2nd engagement) | SA Police | $5.34M |
| Randstad Pty Ltd | Labour resources | Dept for Education | $5.24M |
| Randstad Pty Limited | Admin agency staff | SA Police | $4.98M |
| Hays Specialist Recruitment | Admin agency staff | SA Police | $3.95M |
| Dialog Pty Ltd | IS&T agency staff | SA Police | $3.54M |
| Akkodis Australia Talent | Agency staff services | SA Police | $3.09M |

SAPOL appears in 9 of the top 10 contracts. Most are multi-year agency staff arrangements with no start/end date in the published data.

---

## Top Advisory / Non-Labour-Hire Contractors

Filtering out recruitment and agency staff firms:

| Contractor | Contracts | Total ($M) | Primary Agency |
|-----------|-----------|-----------|----------------|
| Expose Data Pty Ltd | 5 | $2.1M | DHS |
| Fujitsu Australia | 5 | $2.1M | SA Police |
| MEGT (Australia) | 2 | $1.8M | Dept for Education |
| Jacobs Group | 1 | $1.7M | DPC |
| KPMG | 20 | $1.7M | DHS |
| Safeselect | 7 | $1.6M | SA Police |
| Inner Range Pty Ltd | 2 | $1.5M | SA Police |
| Cloudwerx Pty Ltd | 2 | $1.4M | DHS |
| SFDC Australia (Salesforce) | 2 | $1.4M | DHS |
| Fragile To Agile | 3 | $3.1M | SA Police |

KPMG is the highest-volume advisory firm with 20 engagements to DHS. DHS is also a heavy user of technology consultants (Cloudwerx, Salesforce/SFDC, Expose Data).

---

## Value Distribution

| Range | Contracts | Total ($M) |
|-------|-----------|-----------|
| Under $10K | 72 | $0.2M |
| $10K–$50K | 596 | $14.9M |
| $50K–$100K | 189 | $13.1M |
| $100K–$500K | 244 | $53.8M |
| $500K–$1M | 52 | $36.5M |
| Over $1M | 50 | $122.8M |

50 contracts (4% by count) account for $122.8M (51% of total spend). The under-$50K band accounts for 56% of records but only 6% of value.

---

## Data Quality Notes

- **SAPOL (702 contracts):** No start/end dates published. Year cannot be confirmed from the dataset alone.
- **FY coverage:** 432 contracts are confirmed FY2023-24, 69 are FY2024-25. The remainder are undated.
- **No ABN:** SA disclosure policy does not require ABN. Entity matching is by name only — variants like "Randstad Pty Ltd" vs "Randstad Pty Limited" are treated as separate entities.
- **Lotteries Commission values:** 8 records with implausibly small values (e.g. $16) likely published in $000s rather than dollars. Not corrected.
- **SA Health "Total Contractors" ($2.45M):** This is a single aggregate row published by SA Health, not a named contractor. Retained but flagged.

---

## Key Observations

1. **SAPOL is the dominant spender** — $143M of $241M total. Its contractor register reads more like a workforce supplement than a project-by-project engagement log.

2. **Labour hire is the dominant spend category** — $144M (60%). The SA government's reliance on Hays, Randstad, and Paxus for administrative and IS&T staff is significant.

3. **The advisory market is fragmented** — 808 unique contractors with a median value of $41K suggests most engagements are small one-off advisory or specialist assignments, contrasting with the concentrated labour hire top end.

4. **DHS is the most active technology buyer** — Salesforce, Cloudwerx, and Expose Data all appear as significant DHS vendors alongside KPMG for advisory work.

5. **Defence SA is small but active** — 89 contracts totalling $2.9M, mostly small advisory and specialist engagements aligned with defence industry development (average $33K).
