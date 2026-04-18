"""
Generates full HTML analysis reports for Tier A tickers.
Reports are written to docs/reports/TICKER-YYYY-MM-DD.html.

Usage:
    python scripts/generate_reports.py           # all Tier A
    python scripts/generate_reports.py NVDA LLY  # specific tickers
"""

import sys
from datetime import date
from pathlib import Path
from db import get_conn, init_db
from build_site import fmt_exchange

REPORTS_DIR = Path(__file__).parent.parent / "docs" / "reports"

# ── Narrative content per ticker ─────────────────────────────────────────────
# Each entry: thesis, moat, tailwinds, risks, verdict_class (buy/watch/pass), verdict_text

NARRATIVES = {
    "NVDA": {
        "thesis": (
            "NVIDIA dominates AI training and inference compute through the H100, H200, and Blackwell GPU lines "
            "and the CUDA software ecosystem. The combination of hardware and software lock-in constitutes a "
            "platform business with substantial switching costs: CUDA has fifteen years of developer investment, "
            "and re-engineering a training stack for non-NVIDIA hardware is a multi-year effort. "
            "Data center revenue has grown from $15B in FY2024 to $115B in FY2026."
        ),
        "moat": (
            "CUDA developer lock-in is the primary moat. The ecosystem of libraries, toolkits, and trained "
            "engineers makes switching expensive for any organisation with material model training investment. "
            "Hardware supply relationships with TSMC on advanced CoWoS packaging add a manufacturing "
            "constraint that benefits incumbents. GPU market share in AI training is estimated at 80%+."
        ),
        "tailwinds": (
            "Hyperscaler AI infrastructure capex continues to accelerate. Microsoft, Google, Amazon, and Meta "
            "have each guided to material increases in capital expenditure for 2026, with GPU clusters as the "
            "primary allocation. Inference demand is growing as deployed models scale to production workloads, "
            "creating a second growth vector beyond training."
        ),
        "risks": [
            ("China export controls", "Medium", "High", "US revenue diversification; Blackwell ramp in non-restricted markets"),
            ("AMD MI300X adoption", "Low–Medium", "Medium", "CUDA ecosystem depth limits migration for most workloads"),
            ("Hyperscaler custom ASICs", "Low (near-term)", "High (long-term)", "Google TPU, Amazon Trainium address specific workloads only"),
            ("Valuation compression", "Medium", "Medium", "High growth rate provides buffer; fwd P/E already normalised to 18x"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "NVIDIA's revenue has grown from $27B to $216B in three fiscal years. Gross margins have expanded "
            "to 71%. The forward P/E of 18x for a business growing at 65% is the lowest it has traded on a "
            "forward basis in two years. The PEG of 0.72 indicates the market is not pricing in sustained "
            "growth. Initiate a position. Add on any pullback toward the 52-week midpoint."
        ),
        "weight": "8–10%",
    },
    "AVGO": {
        "thesis": (
            "Broadcom supplies custom AI ASICs to three of the largest hyperscalers (Google, Meta, ByteDance) "
            "and holds dominant share in networking silicon for AI clusters through its Tomahawk and Jericho "
            "product lines. The 2023 VMware acquisition adds a recurring enterprise software stream that now "
            "contributes roughly 40% of revenue and improves margin quality."
        ),
        "moat": (
            "Custom ASIC design partnerships are built over years and are deeply embedded in customer roadmaps. "
            "Broadcom co-designs silicon with hyperscalers, creating relationships that are expensive to "
            "displace. Networking silicon holds 60%+ share in merchant Ethernet switching for hyperscale. "
            "VMware's virtualisation stack has high switching costs across the enterprise installed base."
        ),
        "tailwinds": (
            "Custom silicon demand is rising as hyperscalers seek to optimise cost-per-inference on specific "
            "workloads. Broadcom's XPU business is growing faster than total revenue. AI networking upgrades "
            "from 400G to 800G and 1.6T drive continued Tomahawk refresh cycles. VMware revenue is "
            "stabilising following integration and customer renegotiations."
        ),
        "risks": [
            ("Customer concentration", "Medium", "High", "Google and Meta each represent ~20% of revenue; diversification is limited"),
            ("Custom ASIC competition", "Low–Medium", "Medium", "Marvell competing on ASIC design; takes years to displace"),
            ("VMware churn", "Low–Medium", "Medium", "Some customers evaluating alternatives post-acquisition pricing changes"),
            ("Debt load", "Low", "Low", "D/E of 0.83x; strong FCF of $25.5B services debt comfortably"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Broadcom compounds revenue at 24% over three years with 77% gross margins. The fwd P/E of 22x "
            "and PEG of 0.87 represent fair value for a business with this quality of earnings. The VMware "
            "acquisition has absorbed the market's attention; as integration noise fades, the combined "
            "business's recurring revenue profile warrants a higher multiple. Initiate a position."
        ),
        "weight": "6–8%",
    },
    "TSM": {
        "thesis": (
            "Taiwan Semiconductor Manufacturing is the world's leading contract semiconductor foundry and the "
            "sole or primary manufacturer of advanced chips for Apple, NVIDIA, AMD, Qualcomm, and Broadcom. "
            "Every commercially significant AI chip is manufactured at TSMC. The company holds an estimated "
            "2–3 year technology lead over Samsung and Intel on advanced process nodes."
        ),
        "moat": (
            "Process technology leadership at N3 and N2 nodes is not replicable in the short term. "
            "The manufacturing knowledge embedded in TSMC's workforce and processes has compounded over "
            "decades. Equipment procurement, yield optimisation, and customer-specific process tuning create "
            "a moat that is structural, not merely financial. CoWoS advanced packaging capacity is "
            "constrained and TSMC controls the bottleneck for AI chip production."
        ),
        "tailwinds": (
            "AI chip demand drives strong CoWoS advanced packaging utilisation. Arizona fab investment "
            "reduces geopolitical risk for US-based customers and qualifies TSMC for IRA and CHIPS Act "
            "incentives. Smartphone and PC cycle recovery adds a second demand vector alongside AI."
        ),
        "risks": [
            ("Taiwan geopolitical risk", "Low–Medium", "Very high", "Arizona and Japan fabs provide partial diversification over 5+ years"),
            ("Intel foundry competition", "Low (near-term)", "Medium (long-term)", "Intel 18A process unproven at volume; meaningful risk only post-2027"),
            ("Currency (NTD/USD)", "Medium", "Low", "NTD appreciation compresses USD-reported margins; hedged partially"),
            ("Customer concentration", "Medium", "Medium", "Apple and NVIDIA together represent ~40% of revenue"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "TSMC's revenue grew 32% in 2025 (NTD basis) with gross margins expanding to 62% and ROE at 36%. "
            "The forward P/E of 19x and PEG of 1.23 apply a geopolitical discount that is partially deserved "
            "but overstated given Arizona diversification progress. For investors with a 3–5 year horizon, "
            "the foundry monopoly on advanced AI chips makes this a core holding. Initiate a position."
        ),
        "weight": "6–8%",
    },
    "FSLR": {
        "thesis": (
            "First Solar is the only large-scale US manufacturer of solar panels and the primary domestic "
            "beneficiary of IRA Section 45X manufacturing credits. Its cadmium telluride thin-film technology "
            "is produced entirely outside China's supply chain. Manufacturing credits add directly to per-watt "
            "margins, providing structural cost advantages over imported crystalline silicon panels."
        ),
        "moat": (
            "First Solar's CdTe thin-film process requires different manufacturing equipment and expertise "
            "than the crystalline silicon panels produced in China. No large-scale Chinese manufacturer can "
            "quickly replicate it. US tariff policy and IRA domestic content requirements insulate First Solar "
            "from the price competition that has eliminated most Western solar manufacturers. "
            "The book of business (multi-year contracted backlog) provides revenue visibility."
        ),
        "tailwinds": (
            "US data center power demand from AI infrastructure is driving utility-scale solar procurement. "
            "The IRA Section 45X credit generates approximately $0.17 per watt in direct manufacturing "
            "benefit. Reshoring policy benefits are durable across administrations given the bipartisan "
            "support for domestic manufacturing. Power purchase agreement pricing is improving."
        ),
        "risks": [
            ("IRA policy risk", "Low–Medium", "High", "Bipartisan manufacturing support limits rollback risk; some uncertainty remains"),
            ("Module ASP compression", "Medium", "Medium", "Chinese oversupply depresses global panel prices; tariffs partially offset this"),
            ("Capacity execution", "Low–Medium", "Medium", "Rapid expansion to 25GW+ by 2026 carries operational risk"),
            ("Customer concentration", "Medium", "Low", "Long-term supply agreements with utilities limit near-term revenue risk"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "FSLR is the most attractively valued Tier A name on this screen. Revenue has grown from $2.6B "
            "to $5.2B over three years (26% CAGR) and the forward P/E of 7.8x and PEG of 0.49 are "
            "exceptional for a business with this growth profile. The stock is 33% below its 52-week high. "
            "The IRA manufacturing credit provides earnings visibility that the market is underpricing. "
            "Initiate a position. Size reflects policy risk."
        ),
        "weight": "5–7%",
    },
    "LLY": {
        "thesis": (
            "Eli Lilly holds the leading commercial position in GLP-1 receptor agonists through tirzepatide "
            "(Mounjaro for type 2 diabetes, Zepbound for obesity). The global obesity drug market is "
            "projected at $100B+ annually by 2030. Lilly also carries a deep pipeline in oncology "
            "(donanemab, imlunestrant) and immunology that provides growth beyond GLP-1."
        ),
        "moat": (
            "GLP-1 manufacturing scale is a significant barrier. Lilly is investing $9B in domestic "
            "manufacturing capacity and has committed multi-billion dollar expansions in Ireland and Germany. "
            "Tirzepatide's dual GIP/GLP-1 mechanism produces superior weight loss outcomes in SURMOUNT "
            "trial data versus semaglutide, which supports physician and patient preference. "
            "Brand loyalty in a chronic medication context is durable once established."
        ),
        "tailwinds": (
            "Global obesity prevalence (1B+ adults) creates an addressable market that is structural, "
            "not cyclical. SURMOUNT-MMO cardiovascular outcomes data expands the eligible population. "
            "Medicare coverage for obesity indications is expanding. International launches in Japan, "
            "UK, and EU add incremental revenue streams. Oral GLP-1 formulations in development "
            "could further expand the market."
        ),
        "risks": [
            ("Semaglutide competition (NVO)", "High", "Medium", "Ozempic/Wegovy have strong physician loyalty and early market share"),
            ("Supply constraints", "Medium", "High", "Manufacturing ramp has limited commercial uptake; gradually resolving"),
            ("Pricing / reimbursement", "Medium", "High", "Government drug pricing negotiation could compress GLP-1 margins"),
            ("Pipeline failures", "Low–Medium", "High", "Donanemab or key pipeline failures would re-rate the stock materially"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "LLY's revenue grew 45% in fiscal 2025 with 83% gross margins — the highest of any Tier A name "
            "on this screen. The 3-year revenue CAGR of 32% is sustainable given the pipeline and market "
            "size. At $927, the stock is 18% below its 52-week high. The fwd P/E of 22x is reasonable "
            "for the growth trajectory. The D/E of 1.65x is elevated and the main source of caution. "
            "Initiate a position. Monitor FCF conversion as manufacturing capex normalises."
        ),
        "weight": "6–8%",
    },
    "DXCM": {
        "thesis": (
            "DexCom is the market leader in continuous glucose monitoring with the G7 and Stelo platforms. "
            "Revenue is largely recurring through sensor subscriptions, and the installed base generates "
            "high retention. The Stelo OTC product, launched in 2024, expands the addressable market "
            "from insulin-dependent diabetics to pre-diabetics and GLP-1 users monitoring glucose response."
        ),
        "moat": (
            "CGM accuracy, reliability, and clinical validation data create regulatory and clinical "
            "switching costs. The G7's 15-day wear time and integration with insulin pumps, smartwatches, "
            "and pharmacy dispensing systems embed DexCom in patient workflows. "
            "The recurring sensor revenue model provides revenue predictability. "
            "Pharmacy channel distribution (CVS, Walgreens) broadens access beyond DME suppliers."
        ),
        "tailwinds": (
            "GLP-1 drug adoption increases CGM demand: patients on tirzepatide or semaglutide monitor "
            "glucose response as part of weight management. The Type 2 diabetes market is largely "
            "unpenetrated for CGM globally. Stelo's OTC positioning removes the prescription barrier "
            "for the non-insulin segment, which is 5–10x the current CGM-using population."
        ),
        "risks": [
            ("Abbott FreeStyle Libre", "High", "Medium", "Libre has strong international share and is competing on price in the US"),
            ("Reimbursement pressure", "Medium", "High", "CGM coverage policy changes could affect demand from Medicare patients"),
            ("Stelo adoption pace", "Medium", "Medium", "OTC market development takes time; near-term contribution is modest"),
            ("Valuation vs growth", "Low–Medium", "Low", "Fwd P/E 21x is reasonable; PEG 1.34 reflects moderate premium"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "DexCom trades 29% below its 52-week high with the market discounting near-term revenue "
            "guidance resets from 2024. Revenue is growing at 16% YoY with 60% gross margins and 35% ROE. "
            "The GLP-1 tailwind and Stelo OTC expansion are not fully reflected in consensus estimates. "
            "The current price represents a reasonable entry for a high-quality recurring revenue business "
            "with a large and growing addressable market. Initiate a position."
        ),
        "weight": "4–5%",
    },
    "ANET": {
        "thesis": (
            "Arista Networks supplies high-speed Ethernet networking for AI training clusters and hyperscale "
            "data centers. Its EOS (Extensible Operating System) software platform differentiates Arista "
            "from legacy Cisco infrastructure on programmability and operational simplicity. "
            "The shift to AI-scale networking (400G, 800G, and 1.6T) is driving a multi-year upgrade cycle "
            "at Microsoft, Meta, Google, and Oracle."
        ),
        "moat": (
            "EOS is a single-image network operating system deployed across all Arista hardware. "
            "The consistency, reliability record, and programmability in hyperscaler environments "
            "create strong institutional preference. Arista's leadership of the Ultra Ethernet Consortium "
            "positions it as the reference architecture for AI cluster networking. "
            "Near-zero debt and 64% gross margins reflect a business with genuine pricing power."
        ),
        "tailwinds": (
            "AI cluster networking requires low-latency, high-bandwidth fabric that Ethernet is increasingly "
            "capable of delivering at scale. Hyperscaler capex growth drives Arista port shipments. "
            "The 800G to 1.6T transition will require another hardware refresh cycle. "
            "Enterprise campus and WAN segments provide a diversified revenue base outside AI."
        ),
        "risks": [
            ("Valuation", "Medium", "Medium", "Fwd P/E 38x and PEG 2.24 are the primary risk; any growth miss would re-rate sharply"),
            ("Hyperscaler concentration", "Medium", "High", "Microsoft and Meta represent a large share of revenue"),
            ("Cisco competition", "Low–Medium", "Low", "Cisco losing share in hyperscale; remains dominant in enterprise"),
            ("InfiniBand (NVDA)", "Low", "Medium", "NVIDIA's InfiniBand competes in training clusters; Ethernet closing the gap"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Arista grows revenue at 29% YoY with 64% gross margins and effectively no debt. "
            "The near-zero debt balance and $3.4B free cash flow make this the most financially "
            "conservative Tier A name. The fwd P/E of 38x and PEG of 2.24 are elevated and represent "
            "the main risk. Position sizing should be smaller than the other Tier A names to reflect "
            "valuation. Initiate a position. Add on pullbacks toward $140."
        ),
        "weight": "4–5%",
    },
    "PDD": {
        "thesis": (
            "PDD Holdings operates Pinduoduo, China's largest agricultural and value e-commerce platform, "
            "and Temu, the fast-growing international marketplace for discounted manufactured goods. "
            "Revenue grew 59% YoY to $68B with gross margins of 62%, an extraordinary combination for a "
            "company at this scale. The business generates significant free cash flow and carries no net debt. "
            "Temu has rapidly established market presence across the US, EU, and emerging markets by leveraging "
            "direct factory-to-consumer supply chains."
        ),
        "moat": (
            "Pinduoduo's social commerce model — group buying, gamification, and agricultural supply chain "
            "integration — is deeply embedded in rural and lower-tier Chinese city consumer behaviour. "
            "The agricultural procurement network gives Pinduoduo unique cost advantages in fresh produce "
            "that are difficult to replicate. Temu benefits from the same supply chain as Pinduoduo, enabling "
            "price points that Western platforms cannot match without restructuring their cost base."
        ),
        "tailwinds": (
            "Global demand for value merchandise is durable across economic cycles. Temu's marketing spend "
            "is generating substantial brand recognition in developed markets at a pace that rivals early "
            "Amazon international expansion. The agricultural digitalisation opportunity in China remains "
            "largely untapped at the smaller producer level."
        ),
        "risks": [
            ("US–China trade war / tariffs", "High", "High", "Section 301 tariffs and de minimis rule changes directly target Temu's model"),
            ("China regulatory risk", "Medium", "High", "Platform regulation in China remains unpredictable; PDD has faced previous scrutiny"),
            ("ADR / delisting risk", "Low–Medium", "Medium", "US-listed Chinese ADRs carry PCAOB audit and potential delisting risk"),
            ("Temu margin dilution", "Medium", "Medium", "Aggressive marketing spend is subsidising Temu's growth; profitability timeline uncertain"),
        ],
        "verdict": "watch",
        "verdict_text": (
            "PDD is the highest-scoring company on this screen on fundamental metrics alone — 59% revenue "
            "growth, 62% gross margins, 90 screener score — but the geopolitical risk is material and "
            "not fully quantifiable. The de minimis exemption changes and Section 301 tariff escalation "
            "are a direct threat to Temu's unit economics. The business quality is exceptional; the "
            "risk profile warrants a watch posture rather than initiation at full size. "
            "Monitor trade policy developments. Consider a small starter position if tariff risk stabilises."
        ),
        "weight": "0–3%",
    },
    "APP": {
        "thesis": (
            "AppLovin operates AXON, an AI-powered advertising engine that matches mobile app advertisements "
            "to users at scale across a network of 140,000+ mobile apps. Revenue grew 70% YoY to $4.7B "
            "following the AXON 2.0 upgrade in 2024, which dramatically improved targeting accuracy and "
            "monetisation rates. The company is divesting its mobile gaming studio business to focus entirely "
            "on the software platform. Gross margins have expanded toward 75% as the platform mix increases."
        ),
        "moat": (
            "AXON's prediction models are trained on a proprietary data set of mobile app engagement signals "
            "accumulated over a decade. The accuracy of these models compounds with scale: more advertisers "
            "generate more auction data, which improves predictions, which attracts more advertisers. "
            "The data flywheel is the moat. AppLovin's independence from any single app store or walled garden "
            "makes it a neutral infrastructure layer that publishers prefer over Google or Meta alternatives."
        ),
        "tailwinds": (
            "Mobile advertising spend is recovering and growing as app install economics improve. "
            "The post-ATT (App Tracking Transparency) advertising market is consolidating toward platforms "
            "with on-device or first-party data signals — AXON's contextual approach benefits from this. "
            "Expansion into connected TV and e-commerce advertising is an early-stage but large opportunity. "
            "Studio divestiture will improve both margins and investor clarity on the platform business."
        ),
        "risks": [
            ("Platform concentration", "Medium", "High", "Mobile gaming is still the primary advertiser vertical; diversification is early-stage"),
            ("AXON model risk", "Low–Medium", "High", "A significant targeting accuracy regression could cause rapid advertiser churn"),
            ("Regulatory / privacy", "Medium", "Medium", "Increased mobile privacy regulation could reduce signal availability"),
            ("Valuation", "Medium", "Medium", "Revenue growth rate must remain elevated to justify current pricing"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "AppLovin is growing revenue at 70% YoY with gross margins expanding toward 75%. "
            "The AXON 2.0 upgrade has demonstrated that the platform can sustain high growth rates at scale. "
            "The planned gaming studio divestiture will simplify the business and reveal the true software "
            "platform economics. The combination of data-flywheel moat, high margins, and a large underpenetrated "
            "addressable market (e-commerce, CTV) makes this one of the most compelling growth platforms "
            "on this screen. Initiate a position."
        ),
        "weight": "4–6%",
    },
    "INCY": {
        "thesis": (
            "Incyte is a commercial-stage pharmaceutical company focused on oncology and inflammation. "
            "Its primary asset, Jakafi (ruxolitinib), is the standard of care for myelofibrosis and "
            "polycythemia vera — rare blood cancers with no adequate prior treatments. Jakafi's revenue "
            "has grown steadily over twelve years, and the pipeline includes itacitinib (graft-versus-host "
            "disease), pemigatinib (cholangiocarcinoma), and several early-stage immuno-oncology assets."
        ),
        "moat": (
            "Jakafi holds orphan drug status in its approved indications, providing market exclusivity "
            "and premium pricing. The JAK inhibitor class pioneered by ruxolitinib has become the "
            "reference mechanism for myeloproliferative neoplasms, creating deep physician familiarity "
            "and prescribing habit. Royalties from Novartis's ruxolitinib licence (sold as Scemblix) "
            "provide an additional revenue stream. The haematology/oncology specialist salesforce "
            "is difficult and expensive to replicate."
        ),
        "tailwinds": (
            "The myelofibrosis patient population is underdiagnosed and underpenetrated globally. "
            "International Jakafi revenue is growing as regulatory approvals expand in Japan, EU, "
            "and emerging markets. The graft-versus-host disease indication for ruxolitinib (Opzelura) "
            "opens a new patient population. Pipeline assets in atopic dermatitis and vitiligo address "
            "large markets with unmet need."
        ),
        "risks": [
            ("Jakafi patent cliff", "High", "High", "Core Jakafi composition-of-matter patents expire 2027–2028; generics will follow"),
            ("Pipeline execution", "Medium", "High", "Revenue replacement from pipeline requires successful late-stage readouts"),
            ("Competition in JAK inhibitors", "Medium", "Medium", "Abbvie's upadacitinib and Pfizer's tofacitinib compete in inflammation"),
            ("Revenue concentration", "High", "High", "Jakafi represents ~70% of total revenue; patent expiry is an existential transition"),
        ],
        "verdict": "watch",
        "verdict_text": (
            "Incyte's fundamental metrics are excellent — 21% revenue growth, 76% gross margins, "
            "strong balance sheet — but the Jakafi patent cliff arriving in 2027–2028 creates a "
            "binary transition risk. The pipeline must deliver to sustain current revenue levels. "
            "The screener score of 85 reflects trailing strength, not forward visibility. "
            "Watch for Phase 3 pipeline readouts and genericisation timeline updates before initiating. "
            "This is a value opportunity if pipeline assets de-risk, not a growth compounder."
        ),
        "weight": "0–2%",
    },
    "NEM": {
        "thesis": (
            "Newmont is the world's largest gold mining company by production, with operations across "
            "Nevada, Australia, Ghana, Peru, and Canada. Revenue grew 21% YoY to $19B driven by gold "
            "price appreciation. Newmont benefits from structurally elevated gold prices as central banks "
            "globally increase reserves and investors seek inflation hedges. The 2023 Newcrest acquisition "
            "added high-quality copper-gold assets and extended the reserve life of the portfolio."
        ),
        "moat": (
            "Scale in mining creates cost advantages through shared infrastructure, procurement, "
            "and technical expertise. Newmont's tier-one asset base (mines with long reserve lives, "
            "low costs, and stable jurisdictions) commands a premium valuation versus smaller miners. "
            "The gold reserve base provides multi-decade production visibility. However, mining "
            "is fundamentally a commodity business — the moat is operational efficiency, not pricing power."
        ),
        "tailwinds": (
            "Gold prices are supported by central bank reserve diversification away from USD assets, "
            "geopolitical uncertainty, and inflation hedging demand. Copper exposure from the Newcrest "
            "assets provides an additional tailwind from the energy transition (EV motors, grid infrastructure). "
            "All-in sustaining cost (AISC) improvements from portfolio optimisation underway."
        ),
        "risks": [
            ("Gold price cyclicality", "High", "High", "Revenue and earnings are directly levered to gold price; a sustained decline would sharply reduce profits"),
            ("Operational execution", "Medium", "Medium", "Newcrest integration and cost reduction targets carry execution risk"),
            ("Geopolitical / jurisdiction risk", "Medium", "Medium", "Ghana and Peru operations face periodic political uncertainty"),
            ("Capital intensity", "Medium", "Low", "Mining requires continuous reinvestment; free cash flow conversion lags EBITDA"),
        ],
        "verdict": "watch",
        "verdict_text": (
            "Newmont is a well-run business in a sector that passes fundamental filters only when gold "
            "prices are elevated — which they currently are. The high score reflects the current gold price "
            "environment, not a durable business quality advantage. For a portfolio seeking commodity "
            "or inflation diversification, Newmont is the highest-quality vehicle. For a growth-focused "
            "portfolio, the cyclicality and capital intensity are disqualifying. "
            "Watch status: appropriate as a small macro hedge, not a core growth position."
        ),
        "weight": "0–3%",
    },
    "INTU": {
        "thesis": (
            "Intuit operates the dominant small business financial software platform in North America: "
            "QuickBooks (accounting), TurboTax (tax preparation), Credit Karma (personal finance), "
            "and Mailchimp (SMB marketing). Revenue grew 16% YoY to $18B. Intuit Assist, the AI layer "
            "embedded across all products, is automating data entry, anomaly detection, and tax filing "
            "workflows in ways that deepen the switching cost for existing customers and improve "
            "monetisation per user."
        ),
        "moat": (
            "QuickBooks holds 80%+ share of US small business accounting software, a position "
            "built over 35 years of product development and network effects from accountants and bookkeepers "
            "who are trained on and recommend the platform. TurboTax's data advantages compound annually: "
            "prior-year returns pre-populate automatically, making switching to a competitor painful. "
            "Credit Karma's consumer financial data creates a two-sided marketplace with lenders. "
            "These are not easily dislodged positions."
        ),
        "tailwinds": (
            "SMB adoption of cloud-based accounting software is still incomplete — many small businesses "
            "remain on desktop software or spreadsheets. AI automation is increasing the value proposition: "
            "tasks that previously required a bookkeeper can now be handled by Intuit's platform. "
            "International QuickBooks expansion is a long-duration growth vector. "
            "Credit Karma's revenue recovers as consumer lending markets normalise."
        ),
        "risks": [
            ("IRS Direct File", "Medium", "Medium", "Free government tax filing could erode TurboTax's lower-tier market; complexity segments remain protected"),
            ("Credit Karma cyclicality", "Medium", "Medium", "Lending marketplace revenue is sensitive to interest rates and credit availability"),
            ("Valuation", "Low–Medium", "Low", "Fwd P/E 25x and PEG 1.84 represent a fair but not cheap entry point"),
            ("AI commoditisation of tax prep", "Low (near-term)", "Medium (long-term)", "AI could lower barriers to entry in tax software over the next decade"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Intuit compounds revenue at 14% CAGR over three years with 80% gross margins and 20% ROE. "
            "The AI integration is not speculative — Intuit Assist is live across all products and is "
            "measurably reducing support costs and improving retention. The multi-product platform "
            "with deep switching costs is the archetype of durable software economics. "
            "At a fwd P/E of 25x, the valuation is reasonable for this quality. Initiate a position."
        ),
        "weight": "4–5%",
    },
    "PTC": {
        "thesis": (
            "PTC provides product lifecycle management (PLM) and industrial IoT software to manufacturers "
            "globally. Its flagship platforms — Windchill (PLM), Creo (CAD), ThingWorx (IIoT), and "
            "Vuforia (augmented reality) — are deeply embedded in engineering and manufacturing workflows "
            "at aerospace, defence, automotive, and industrial customers. Revenue grew 19% YoY as the "
            "business completed its transition from perpetual licences to recurring SaaS and "
            "subscription contracts."
        ),
        "moat": (
            "PLM software is the system of record for product design data. Migrating a 20-year product "
            "history from Windchill to a competitor system is a multi-year, high-risk undertaking that "
            "most enterprise customers avoid indefinitely. Creo CAD is similarly sticky — engineers build "
            "careers on specific CAD tools, and retraining is costly. Regulatory compliance requirements "
            "in aerospace and medical device manufacturing further lock in PTC's platforms."
        ),
        "tailwinds": (
            "Digital thread and digital twin adoption is accelerating across manufacturing as companies "
            "connect physical production with design data. IIoT monitoring of manufacturing equipment "
            "is an early-stage but large opportunity. Defence spending growth in NATO countries benefits "
            "PTC's large aerospace and defence customer base. "
            "ServiceMax (field service management) adds a post-sale service revenue stream."
        ),
        "risks": [
            ("Siemens and Dassault competition", "Medium", "Medium", "Both offer comparable PLM suites with strong enterprise relationships"),
            ("Transition execution", "Low", "Low", "Subscription transition substantially complete; ARR growth is the relevant metric"),
            ("Customer concentration", "Medium", "Low", "Aerospace and defence is a significant vertical; sector downturns would affect PTC"),
            ("Valuation", "Low–Medium", "Low", "Fwd P/E 25x and PEG 1.23 are reasonable for a recurring revenue industrial software business"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "PTC is the least well-known name on the Tier A list but one of the most defensively positioned. "
            "Industrial PLM and IIoT software has some of the highest switching costs in enterprise software. "
            "Revenue grows at 19% YoY with 83% gross margins and a fully transitioned SaaS model. "
            "The fwd P/E of 25x and PEG of 1.23 are among the most attractive on this screen for the "
            "quality of the business. Initiate a position."
        ),
        "weight": "3–5%",
    },
    "TTD": {
        "thesis": (
            "The Trade Desk operates the largest independent demand-side platform (DSP) for programmatic "
            "advertising, serving agencies and brands that buy digital advertising inventory across "
            "connected TV, mobile, display, and audio. Revenue grew 18.5% YoY to $2.4B. The company's "
            "independence from any walled garden (it does not own media inventory) positions it as the "
            "neutral infrastructure layer that agencies prefer for cross-channel planning. "
            "Unified ID 2.0 (UID2) is becoming an industry-standard identity solution for cookieless targeting."
        ),
        "moat": (
            "The Trade Desk's data flywheel: more advertisers generate more bid data, improving prediction "
            "models, which deliver better campaign outcomes, which attract more advertisers. "
            "Independence from publisher inventory (unlike Google's DV360) is a genuine differentiator — "
            "agencies trust TTD with cross-media budget allocation because it has no conflict of interest. "
            "UID2 adoption creates a standards-level network effect that benefits the platform long-term."
        ),
        "tailwinds": (
            "Connected TV advertising is shifting spend from linear broadcast as streaming viewership "
            "grows and measurement capabilities improve. The Trade Desk is the leading DSP for CTV "
            "programmatic buying. Third-party cookie deprecation is driving demand for identity solutions "
            "like UID2. Retail media networks are integrating with TTD's platform to offer first-party "
            "purchase data for targeting."
        ),
        "risks": [
            ("Google competition", "High", "High", "Google's DV360 benefits from YouTube inventory access TTD cannot match"),
            ("CTV deal dependency", "Medium", "Medium", "Netflix, Disney+, and major streamers could exclude independent DSPs"),
            ("Valuation", "Medium", "Medium", "Fwd P/E 35x is elevated; any growth deceleration would re-rate sharply"),
            ("Cookie timelines", "Low", "Low", "Cookie deprecation delays reduce urgency of UID2 adoption by publishers"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "The Trade Desk is the best-positioned independent advertising technology platform in the "
            "market. Revenue grows at 18.5% YoY with 81% gross margins and a strong net cash balance sheet. "
            "CTV is still in the early innings of programmatic adoption — the addressable market is expanding "
            "faster than TTD's current growth rate implies. The fwd P/E of 35x is the primary risk, but "
            "for a business with genuine platform moat in a large and growing market, it is justifiable. "
            "Initiate a position."
        ),
        "weight": "3–5%",
    },
    "DECK": {
        "thesis": (
            "Deckers Outdoor is the parent company of HOKA (performance running footwear) and UGG "
            "(premium sheepskin boots). HOKA is the primary growth engine: revenue has grown from under "
            "$400M to over $2B in five years, taking meaningful market share from established athletic "
            "brands in the performance running category. UGG provides stable, high-margin revenue with "
            "brand durability across decades. Deckers carries no long-term debt and generates strong "
            "free cash flow."
        ),
        "moat": (
            "HOKA's midsole geometry and cushioning technology have created a distinctive product that "
            "commands premium pricing ($130–$250) while maintaining strong sell-through at retail. "
            "Professional running community endorsement and podiatric clinical preference have driven "
            "word-of-mouth adoption that advertising cannot replicate easily. "
            "UGG's brand equity in premium comfort footwear has proven durable across fashion cycles "
            "since the 1970s. Both brands have high repeat purchase rates."
        ),
        "tailwinds": (
            "HOKA is expanding from core running into trail, hiking, and lifestyle categories — each "
            "representing meaningful TAM expansion beyond competitive road running. International "
            "penetration for HOKA is early: Europe and Asia are significantly underpenetrated. "
            "DTC (direct-to-consumer) channel growth is improving margins. The premium outdoor and "
            "performance footwear category is growing faster than broad athletic footwear."
        ),
        "risks": [
            ("HOKA brand momentum", "Medium", "High", "Brand heat in footwear is difficult to sustain; early Nike and UA trajectories show eventual deceleration"),
            ("UGG fashion cyclicality", "Medium", "Medium", "UGG's appeal has proven durable, but is not immune to trend risk"),
            ("Wholesale dependency", "Medium", "Low", "Significant revenue through third-party retail creates margin and inventory risk"),
            ("Competition from incumbents", "Medium", "Medium", "Nike, Adidas, and On Running are all investing in the cushioning/performance category"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Deckers is the most straightforward consumer quality name on this screen. No debt, "
            "30% EPS growth, 16% revenue CAGR, and two brands with genuine consumer loyalty. "
            "HOKA's international expansion provides a runway that the market is not fully pricing. "
            "The fwd P/E of 11x for a business of this quality represents an attractive entry point. "
            "Initiate a position."
        ),
        "weight": "3–5%",
    },
    "MU": {
        "thesis": (
            "Micron Technology manufactures DRAM and NAND flash memory — the storage and working memory "
            "that every computing system requires. Revenue grew 49% YoY to $35B as the memory cycle "
            "recovered sharply from the 2023 trough. The key forward narrative is High Bandwidth Memory "
            "(HBM): Micron is the third supplier of HBM alongside Samsung and SK Hynix, and its HBM3E "
            "has been qualified and is shipping to NVIDIA for H200 and Blackwell GPU platforms. "
            "HBM commands 5–8x the ASP of standard DRAM."
        ),
        "moat": (
            "Memory manufacturing requires mastery of sub-5nm lithography, advanced packaging, and "
            "yield optimisation processes accumulated over decades. The three-supplier oligopoly "
            "(Samsung, SK Hynix, Micron) creates a structurally disciplined supply market compared to "
            "historical cycles when excess entrants caused prolonged oversupply. "
            "HBM supply constraints are manufacturing-limited: CoW (chip-on-wafer) stacking yield is "
            "difficult to scale quickly, creating a natural barrier to rapid supply increases."
        ),
        "tailwinds": (
            "AI model inference requires increasing HBM capacity per GPU as context windows expand. "
            "Micron is supply-constrained on HBM through 2025–2026 based on customer communications. "
            "PC and smartphone end markets are in a replacement cycle after a prolonged downturn. "
            "Data center DRAM demand is secular, not cyclical."
        ),
        "risks": [
            ("Cycle peak timing", "High", "High", "Memory is deeply cyclical; the current upcycle will eventually turn — timing is unknowable"),
            ("Samsung capex response", "Medium", "High", "Samsung has historically flooded supply during upcycles; HBM discipline is newer and less tested"),
            ("China competition", "Low–Medium", "Medium", "CXMT is expanding DRAM capacity aggressively but remains behind on advanced nodes"),
            ("Execution on HBM ramp", "Low–Medium", "High", "HBM yield improvements and capacity ramp are critical to the investment thesis"),
        ],
        "verdict": "watch",
        "verdict_text": (
            "Micron scores 80 on the screener because the memory cycle is currently in an upcycle — "
            "the same screen in 2023 would have placed Micron in Tier D. The HBM story is real: "
            "Micron is a qualified supplier for NVIDIA's most critical products, and HBM economics "
            "are structurally better than commodity DRAM. But timing the memory cycle is notoriously "
            "difficult. Watch status: monitor HBM capacity ramp progress and any signs of DRAM "
            "oversupply in commodity segments. Consider a small position sized for cyclicality."
        ),
        "weight": "2–4%",
    },
    "NOW": {
        "thesis": (
            "ServiceNow provides cloud-based enterprise workflow automation, with the Now Platform "
            "serving as the operating system for IT service management, HR, legal, finance, and "
            "customer operations. Revenue grew 21% YoY to $11B. The AI transition is ServiceNow's "
            "primary growth accelerator: Now Assist embeds generative AI across every workflow module, "
            "increasing per-seat value and driving upsell on the existing installed base. "
            "The platform's horizontal applicability across departments has enabled ServiceNow to "
            "expand far beyond its original IT helpdesk origins."
        ),
        "moat": (
            "ServiceNow is the system of record for IT operations at large enterprises. Once workflows, "
            "approvals, and integrations are built on the Now Platform, migrating them is a multi-year "
            "re-engineering project. The platform's configurability — allowing non-developers to build "
            "workflows — creates internal champions across business units who resist displacement. "
            "Renewal rates above 98% reflect the depth of this operational embedding."
        ),
        "tailwinds": (
            "AI Agents built on the Now Platform are automating tasks that previously required human "
            "intervention: L1 IT support, HR onboarding, contract approvals. Each agent increases the "
            "value of the platform without requiring incremental headcount from the customer. "
            "Government and regulated-industry adoption is accelerating as FedRAMP authorisation "
            "expands. The Pro Plus and Enterprise Plus AI tiers carry materially higher ASPs."
        ),
        "risks": [
            ("Valuation", "High", "Medium", "Fwd P/E 50x+ is pricing in sustained high growth; any deceleration would be severely punished"),
            ("Salesforce and Microsoft competition", "Medium", "Medium", "Both are investing in workflow automation — Microsoft via Power Platform, Salesforce via Flow"),
            ("Execution on AI monetisation", "Low–Medium", "High", "Now Assist adoption must convert to measurable ARR expansion to justify the multiple"),
            ("Macro sensitivity", "Medium", "Low", "IT budget cuts disproportionately affect software renewals in a downturn"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "ServiceNow is the highest-quality enterprise software franchise on this screen after Microsoft. "
            "21% revenue growth, 79% gross margins, 98%+ renewal rates, and a platform that becomes "
            "more valuable with every AI capability added. The fwd P/E of 50x+ is the obvious risk — "
            "this is only appropriate at a position size that reflects the valuation premium. "
            "Initiate a smaller position than the balance sheet quality alone would suggest. "
            "Add on any significant pullback."
        ),
        "weight": "3–5%",
    },
    "MSFT": {
        "thesis": (
            "Microsoft is the dominant enterprise technology platform across cloud (Azure), productivity "
            "(Microsoft 365), developer tools (GitHub), gaming (Xbox), and AI (Copilot). Azure is the "
            "second-largest public cloud by revenue and growing at 31% — faster than the overall company "
            "revenue growth of 15%. Copilot is embedded across Microsoft 365, GitHub, Azure, and Dynamics, "
            "creating an AI upsell layer across the entire product portfolio. Microsoft holds a 49% stake "
            "in OpenAI and exclusive rights to GPT model deployment in Azure."
        ),
        "moat": (
            "The Microsoft 365 suite (Outlook, Teams, Word, Excel, SharePoint) is the default productivity "
            "environment for the global enterprise. Switching costs are generational — entire organisations "
            "are trained on and operationally dependent on Microsoft tools. Azure benefits from enterprise "
            "trust, compliance certifications, and hybrid cloud integration with Windows Server estates. "
            "GitHub holds 90%+ of developer workflow activity for hosted code. The combination of these "
            "positions makes Microsoft the widest-moat technology company in the world."
        ),
        "tailwinds": (
            "Azure's growth rate is accelerating as AI workloads migrate to cloud. Copilot for Microsoft 365 "
            "at $30/user/month represents a 25–30% premium to base M365 pricing — adoption at even modest "
            "rates adds billions in incremental ARR. GitHub Copilot is the most widely adopted AI coding "
            "assistant. Azure OpenAI is the primary enterprise API for GPT-4 and GPT-4o deployments."
        ),
        "risks": [
            ("Antitrust / regulatory", "Medium", "Low", "EU and US scrutiny of Teams bundling and AI market position is ongoing"),
            ("OpenAI dependency", "Low–Medium", "Medium", "Exclusive Azure relationship could change if OpenAI's corporate structure evolves"),
            ("Azure growth deceleration", "Low–Medium", "High", "Any slowdown in Azure growth rate would re-rate the stock materially"),
            ("Valuation at scale", "Low", "Low", "Fwd P/E 23x for the quality and breadth of the franchise is not demanding"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Microsoft is the foundational enterprise technology holding for any portfolio. "
            "The Copilot upsell cycle is still in early adoption phases and represents a "
            "multi-billion dollar incremental revenue opportunity on an already massive base. "
            "At a fwd P/E of 23x, the stock is valued in line with the S&P 500 despite "
            "materially superior growth and moat characteristics. "
            "Initiate a position. This is a core holding — size it accordingly."
        ),
        "weight": "8–10%",
    },
    "BSX": {
        "thesis": (
            "Boston Scientific develops medical devices across electrophysiology, endoscopy, urology, "
            "and neuromodulation. Revenue grew 20% YoY to $16B. The two primary growth drivers are "
            "WATCHMAN FLX (left atrial appendage closure for atrial fibrillation patients who cannot "
            "take anticoagulants) and FARAPULSE (pulsed field ablation for AF). Both are taking share "
            "from surgical and drug-based alternatives in large and growing patient populations."
        ),
        "moat": (
            "Medical device companies with clinically differentiated products build procedural moats: "
            "physicians trained on a specific technique are reluctant to switch. The WATCHMAN procedure "
            "requires specialised catheter lab training and patient selection expertise that creates "
            "durable physician and hospital preference. FARAPULSE's pulsed field ablation technology "
            "offers a safer tissue-selective ablation profile than radiofrequency — "
            "clinical differentiation that supports pricing power."
        ),
        "tailwinds": (
            "Atrial fibrillation prevalence increases with age — the ageing of the global population "
            "is a structural demand driver for both WATCHMAN and FARAPULSE. Oral anticoagulant "
            "alternatives carry bleeding risk that the WATCHMAN procedure eliminates, expanding the "
            "eligible patient pool. Pulsed field ablation is replacing radiofrequency ablation "
            "as the preferred energy modality — BSX is the market leader in PFA."
        ),
        "risks": [
            ("Reimbursement policy", "Medium", "High", "CMS coverage determinations for WATCHMAN expansions are a gating factor"),
            ("Medtronic and Abbott competition", "Medium", "Medium", "Both competitors are developing competing LAA closure and PFA devices"),
            ("Integration execution", "Low", "Low", "BSX has an active M&A strategy; integration risk is managed but real"),
            ("Debt level", "Low–Medium", "Low", "D/E of 0.73x is manageable with strong FCF; acquisition history adds complexity"),
        ],
        "verdict": "buy",
        "verdict_text": (
            "Boston Scientific is growing revenue at 20% YoY — exceptional for a large-cap medtech — "
            "with WATCHMAN and FARAPULSE in the early-to-mid stages of their adoption curves. "
            "The EP (electrophysiology) market is large, growing, and BSX holds leading positions "
            "in the two most important new procedural categories. "
            "At a fwd P/E of 25x, the valuation is appropriate for the growth trajectory. "
            "Initiate a position."
        ),
        "weight": "3–5%",
    },
    "NVMI": {
        "thesis": (
            "Nova Ltd. provides metrology and process control equipment to semiconductor manufacturers. "
            "Its optical and X-ray measurement tools verify that chip dimensions and material properties "
            "meet specifications during and after fabrication — a quality control step that is mandatory "
            "at every process node. Revenue grew 31% YoY. Nova's customers include TSMC, Samsung, "
            "Intel, and all major memory manufacturers. As process nodes shrink below 3nm, measurement "
            "accuracy requirements become more stringent, increasing Nova's value per wafer."
        ),
        "moat": (
            "Process control equipment is highly specialised and validated against specific process "
            "recipes at each customer fab. Switching a metrology tool requires re-qualification of the "
            "process — a costly and time-consuming activity that customers avoid without strong reason. "
            "Nova's technical expertise in optical metrology and its OCD (optical critical dimension) "
            "measurement algorithms are developed in close collaboration with leading-edge fabs. "
            "The company holds a strong position alongside KLA Corporation at the most advanced nodes."
        ),
        "tailwinds": (
            "Advanced node transitions (5nm → 3nm → 2nm) require more metrology steps per wafer, "
            "not fewer — Nova's revenue per wafer increases with complexity. Gate-all-around (GAA) "
            "transistors and backside power delivery at 2nm nodes create new measurement challenges "
            "that Nova's tools are designed to address. Memory HBM and advanced DRAM nodes similarly "
            "require denser metrology coverage. Fab capacity expansions globally add new tool purchases."
        ),
        "risks": [
            ("Customer concentration", "High", "Medium", "TSMC alone represents a large share of revenue; any capex pause would affect Nova"),
            ("KLA competition", "Medium", "Medium", "KLA is the dominant metrology and process control supplier with far greater scale"),
            ("Illiquidity / small cap", "Medium", "Low", "Nova is a ~$4B market cap Israeli company with lower liquidity than peers"),
            ("Export controls", "Low–Medium", "Medium", "US export control changes affecting chip equipment could impact sales to certain customers"),
        ],
        "verdict": "watch",
        "verdict_text": (
            "Nova is the highest-quality small-cap idea on this screen — 31% revenue growth, 54% gross "
            "margins, essentially no debt, and an irreplaceable position in the semiconductor equipment "
            "supply chain. The primary concerns are KLA's dominant market position in the broader "
            "metrology category and the smaller cap / liquidity profile. "
            "Watch status reflects size and concentration risks. A position is warranted for "
            "portfolios comfortable with small-cap exposure to semiconductor capex."
        ),
        "weight": "1–3%",
    },
}


# ── HTML generation ──────────────────────────────────────────────────────────

CSS = open(Path(__file__).parent.parent / "scripts" / "build_site.py").read().split("CSS = \"\"\"")[1].split('"""')[0]

THEME_INIT = '<script>const t=localStorage.getItem("pythia-theme");if(t)document.documentElement.setAttribute("data-theme",t);</script>'

THEME_JS = """
<script>
  function toggleTheme() {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('pythia-theme', next);
    document.querySelector('.theme-toggle').textContent = next === 'dark' ? 'Light' : 'Dark';
  }
  document.addEventListener('DOMContentLoaded', function() {
    const theme = document.documentElement.getAttribute('data-theme');
    const btn = document.querySelector('.theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? 'Light' : 'Dark';
  });
</script>"""


def shell(title, body):
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Pythia</title>
  {THEME_INIT}
  <style>{CSS}
    .prose {{ color:var(--text); font-size:14px; line-height:1.8; }}
    .prose p {{ margin-bottom:12px; }}
  </style>
</head>
<body>
{body}
{THEME_JS}
</body>
</html>"""


def fmt_large(v):
    if v is None: return "—"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def fmt_pct(v):  return f"{v*100:.1f}%" if v is not None else "—"
def fmt_x(v):    return f"{v:.1f}x" if v is not None else "—"
def fmt_num(v, dp=2): return f"{v:,.{dp}f}" if v is not None else "—"


def generate(ticker: str, conn):
    nav = NARRATIVES.get(ticker)
    if not nav:
        print(f"  [{ticker}] no narrative — skipped")
        return

    c  = conn.execute("SELECT * FROM companies WHERE ticker=?", (ticker,)).fetchone()
    f  = conn.execute("SELECT * FROM fundamentals WHERE ticker=? ORDER BY snapshot_date DESC LIMIT 1", (ticker,)).fetchone()
    sr = conn.execute("SELECT * FROM screen_results WHERE ticker=?", (ticker,)).fetchone()
    pr = conn.execute("SELECT close FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1", (ticker,)).fetchone()
    hi = conn.execute("SELECT MAX(high) as h, MIN(low) as l FROM prices WHERE ticker=? AND date >= date('now','-365 days')", (ticker,)).fetchone()
    news = conn.execute("SELECT * FROM news WHERE ticker=? ORDER BY published_at DESC LIMIT 6", (ticker,)).fetchall()

    name     = (c and c["name"]) or ticker
    sector   = (c and c["sector"]) or "—"
    industry = (c and c["industry"]) or "—"
    exchange = fmt_exchange(c and c["exchange"])
    price   = pr["close"] if pr else None
    h52     = hi["h"] if hi else None
    l52     = hi["l"] if hi else None
    today   = date.today().isoformat()
    fund_date = (f and f["snapshot_date"]) or "unknown"

    last_fetch = conn.execute("""
        SELECT fetched_at FROM data_audit
        WHERE ticker = ? AND endpoint = 'info' ORDER BY fetched_at DESC LIMIT 1
    """, (ticker,)).fetchone()
    fetch_date = last_fetch["fetched_at"][:10] if last_fetch else "unknown"

    pct_from_high = f"{((price - h52) / h52 * 100):.1f}%" if price and h52 else "—"

    snap = f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-label">Price</div><div class="stat-value neutral">${fmt_num(price)}</div><div class="stat-sub">{pct_from_high} from 52w high</div></div>
  <div class="stat-card"><div class="stat-label">52w Range</div><div class="stat-value neutral" style="font-size:16px">${fmt_num(l52)} – ${fmt_num(h52)}</div><div class="stat-sub">&nbsp;</div></div>
  <div class="stat-card"><div class="stat-label">Market Cap</div><div class="stat-value neutral" style="font-size:18px">{fmt_large(f and f['market_cap'])}</div><div class="stat-sub">&nbsp;</div></div>
  <div class="stat-card"><div class="stat-label">Revenue (ttm)</div><div class="stat-value neutral" style="font-size:16px">{fmt_large(f and f['revenue_ttm'])}</div><div class="stat-sub">Growth: {fmt_pct(sr and sr['revenue_growth_yoy'])}</div></div>
  <div class="stat-card"><div class="stat-label">Gross Margin</div><div class="stat-value neutral">{fmt_pct(f and f['gross_margin'])}</div><div class="stat-sub">Net margin: {fmt_pct(f and f['net_margin'])}</div></div>
  <div class="stat-card"><div class="stat-label">FCF (ttm)</div><div class="stat-value neutral" style="font-size:18px">{fmt_large(f and f['free_cashflow'])}</div><div class="stat-sub">FCF yield: {fmt_pct((f['free_cashflow']/f['market_cap']) if f and f['free_cashflow'] and f['market_cap'] else None)}</div></div>
  <div class="stat-card"><div class="stat-label">Fwd P/E</div><div class="stat-value neutral">{fmt_x(f and f['fwd_pe'])}</div><div class="stat-sub">PEG: {fmt_num(f and f['peg_ratio'])}</div></div>
  <div class="stat-card"><div class="stat-label">ROE</div><div class="stat-value neutral">{fmt_pct(f and f['roe'])}</div><div class="stat-sub">D/E: {fmt_num(f and f['debt_to_equity'])}</div></div>
  <div class="stat-card"><div class="stat-label">Screen Score</div><div class="stat-value neutral">{sr['score']:.0f} <span style="font-size:14px;font-weight:normal">/ 100</span></div><div class="stat-sub">Tier: <span class="badge A">A</span></div></div>
</div>
<div style="margin-top:10px;font-size:11px;color:var(--text-dim)">
  Structured data: <strong>yfinance</strong> &nbsp;·&nbsp; Fetched: <strong>{fetch_date}</strong> &nbsp;·&nbsp; Snapshot: <strong>{fund_date}</strong>
  &nbsp;·&nbsp; <a href="../profiles/{ticker}.html" style="color:var(--text-dim)">View raw profile →</a>
</div>"""

    score_table = f"""
<div class="sub-label">Score breakdown</div>
<table>
  <thead><tr><th>Category</th><th class="num">Score</th><th class="num">Max</th></tr></thead>
  <tbody>
    <tr><td>Growth</td>        <td class="num accent">{sr['score_growth']:.0f}</td>        <td class="num dim">30</td></tr>
    <tr><td>Profitability</td> <td class="num accent">{sr['score_profitability']:.0f}</td>  <td class="num dim">25</td></tr>
    <tr><td>Valuation</td>     <td class="num accent">{sr['score_valuation']:.0f}</td>      <td class="num dim">25</td></tr>
    <tr><td>Balance Sheet</td> <td class="num accent">{sr['score_balance_sheet']:.0f}</td>  <td class="num dim">20</td></tr>
  </tbody>
</table>"""

    risk_rows = "".join(f"""
    <tr><td>{r}</td><td class="dim">{l}</td><td class="dim">{i}</td><td class="dim">{m}</td></tr>"""
        for r, l, i, m in nav["risks"])

    risk_table = f"""
<table>
  <thead><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigant</th></tr></thead>
  <tbody>{risk_rows}</tbody>
</table>"""

    news_html = ""
    for n in news:
        summ = n["summary"] or ""
        news_html += f"""
<div class="news-item">
  <div class="news-headline"><a href="{n['url'] or '#'}" target="_blank" rel="noopener">{n['title'] or ''}</a></div>
  <div class="news-meta"><span class="source">{n['source'] or ''}</span> &nbsp;·&nbsp; {(n['published_at'] or '')[:10]}</div>
  {'<div class="news-summary">' + summ[:220] + '</div>' if summ else ''}
</div>"""

    verdict_class = nav["verdict"]
    verdict_label = {"buy": "BUY", "watch": "WATCH", "pass": "PASS"}[verdict_class]

    body = f"""
<a class="back-link" href="../dashboard.html">← Back to dashboard</a>

<header class="site-header">
  <div class="site-header-row">
    <div>
      <div class="label">Pythia — Analysis Report</div>
      <h1>{ticker} &mdash; {name}</h1>
      <div class="meta">
        {f'<span style="font-weight:600">{exchange}: {ticker}</span> &nbsp;·&nbsp; ' if exchange else ''}Sector: <span>{sector}</span> &nbsp;·&nbsp;
        Industry: <span>{industry}</span> &nbsp;·&nbsp;
        Generated: <span>{today}</span>
      </div>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">Dark</button>
  </div>
  <nav>
    <a href="../index.html">Home</a>
    <a href="../dashboard.html">Dashboard</a>
  </nav>
</header>

<section>
  <div class="section-title">Snapshot</div>
  {snap}
  {score_table}
</section>

<section>
  <div class="section-title">Investment Thesis</div>
  <div class="callout blue"><div class="prose"><p>{nav['thesis']}</p></div></div>
</section>

<section>
  <div class="section-title">Fundamental Analysis</div>
  <div class="sub-label" style="margin-top:0">Competitive Position</div>
  <div class="callout"><div class="prose"><p>{nav['moat']}</p></div></div>
  <div class="sub-label">Macro Tailwinds</div>
  <div class="callout blue"><div class="prose"><p>{nav['tailwinds']}</p></div></div>
</section>

<section>
  <div class="section-title">Risks</div>
  {risk_table}
</section>

<section>
  <div class="section-title">Recent News</div>
  {news_html or '<p style="color:var(--text-dim);font-size:13px">No news stored.</p>'}
</section>

<section>
  <div class="section-title">Verdict</div>
  <div class="verdict-block">
    <div class="verdict-row">
      <div><div class="verdict-label">Recommendation</div></div>
      <span class="badge {verdict_class}">{verdict_label}</span>
      <div style="margin-left:auto;color:var(--text-dim);font-size:12px">
        Suggested weight: <strong style="color:var(--text)">{nav['weight']}</strong>
      </div>
    </div>
    <div class="verdict-body prose"><p>{nav['verdict_text']}</p></div>
  </div>
</section>

<footer class="report-footer">
  Pythia &nbsp;·&nbsp; {ticker} Analysis Report &nbsp;·&nbsp; {today} &nbsp;·&nbsp; <a href="https://fancyboy96.github.io/trader/methodology.html">Methodology</a> &nbsp;·&nbsp; For personal use only
  <div style="margin-top:10px;font-size:11px;color:var(--text-dim);line-height:1.6;max-width:800px">This report is produced for personal research purposes only. Nothing here constitutes financial advice, an investment recommendation, or an offer to buy or sell any security. All data is sourced from public APIs and may be inaccurate, delayed, or incomplete. Past performance is not indicative of future results. Do your own research. Consult a licensed financial adviser before making any investment decision.</div>
</footer>"""

    path = REPORTS_DIR / f"{ticker}-{today}.html"
    path.write_text(shell(f"{ticker} — {name}", body))
    print(f"  [{ticker}] {path.name}")


def main():
    init_db()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()

    tickers = sys.argv[1:] if len(sys.argv) > 1 else [
        r["ticker"] for r in conn.execute(
            "SELECT ticker FROM screen_results WHERE tier='A' AND passed_filters=1 ORDER BY score DESC"
        ).fetchall()
    ]

    print(f"Generating reports for: {', '.join(tickers)}")
    for t in tickers:
        generate(t, conn)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
