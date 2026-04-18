"""
Investment plays — curated thematic ideas.

Each play is a dict with:
  id       : URL-safe slug (used as filename)
  title    : Display name
  status   : "active" | "watch" | "closed"
  summary  : One-line description for the index table
  thesis   : Full rationale paragraph(s)
  tickers  : List of tickers included in the play (must exist in DB)
  added    : ISO date the play was created
"""

PLAYS = [
    {
        "id": "ai-infrastructure",
        "title": "AI Infrastructure",
        "status": "active",
        "summary": "The physical layer powering the AI buildout — chips, networking, and foundry capacity.",
        "thesis": (
            "Hyperscaler capital expenditure on AI compute reached record levels in 2025 and shows no sign of slowing. "
            "The beneficiaries are concentrated: NVIDIA dominates GPU supply, Broadcom supplies custom ASICs and high-speed networking, "
            "TSMC manufactures the leading-edge silicon for both, and Arista Networks provides the spine switching that connects GPU clusters. "
            "All four sit at structural chokepoints in the supply chain with high switching costs and pricing power. "
            "The play is long the physical infrastructure layer before AI software margins materialise broadly."
        ),
        "tickers": ["NVDA", "AVGO", "TSM", "ANET"],
        "added": "2026-04-18",
    },
    {
        "id": "glp1-metabolic-health",
        "title": "GLP-1 & Metabolic Health",
        "status": "active",
        "summary": "Obesity and diabetes drug demand driving a multi-decade healthcare platform shift.",
        "thesis": (
            "GLP-1 receptor agonists represent the first pharmacological intervention shown to reliably reduce body weight at scale. "
            "Eli Lilly's tirzepatide (Mounjaro / Zepbound) leads on efficacy data and has a growing manufacturing base. "
            "DexCom benefits from the same chronic disease population: continuous glucose monitoring is standard of care for Type 1 diabetes "
            "and increasingly adopted in Type 2, with the GLP-1 wave expanding the addressable patient pool. "
            "Both companies have durable IP, recurring revenue, and are early in global penetration curves."
        ),
        "tickers": ["LLY", "DXCM"],
        "added": "2026-04-18",
    },
    {
        "id": "quantum-computing",
        "title": "Quantum Computing",
        "status": "watch",
        "summary": "Early-stage quantum hardware and the established tech platforms building serious quantum programs.",
        "thesis": (
            "Quantum computing is moving from laboratory demonstration to early commercial availability. "
            "The play spans two distinct risk profiles. "
            "At the speculative end, IonQ, Rigetti, and D-Wave are pure-play hardware companies building trapped-ion and superconducting systems; "
            "all are pre-scale on revenue and will not pass conventional fundamental filters, but they hold the most direct exposure to a hardware breakthrough. "
            "At the established end, Microsoft's topological qubit program (Azure Quantum) and Google's Willow chip represent well-funded, "
            "long-horizon bets from companies that can absorb the capital cost. IBM has the most mature end-to-end quantum stack with IBM Quantum, "
            "though its current balance sheet is under near-term pressure. "
            "The watch status reflects genuine commercial uncertainty: quantum advantage over classical compute has not been demonstrated "
            "for practical business problems at scale. Position sizing should reflect that asymmetry."
        ),
        "tickers": ["MSFT", "GOOGL", "IBM", "IONQ", "RGTI", "QBTS"],
        "added": "2026-04-18",
    },
    {
        "id": "clean-energy-transition",
        "title": "Clean Energy Transition",
        "status": "watch",
        "summary": "Utility-scale solar manufacturing with US domestic content advantages under IRA incentives.",
        "thesis": (
            "First Solar is the only large-scale US-headquartered manufacturer of thin-film solar modules, "
            "a position that earns it preferential treatment under the Inflation Reduction Act's domestic content bonus credits. "
            "Its cadmium telluride technology is polysilicon-free, insulating it from Chinese supply chain exposure that affects most competitors. "
            "Utility-scale demand in the US is structurally driven by data centre electrification and grid decarbonisation targets. "
            "The watch status reflects near-term policy uncertainty around IRA credits — the thesis is intact but entry timing matters."
        ),
        "tickers": ["FSLR"],
        "added": "2026-04-18",
    },
]
