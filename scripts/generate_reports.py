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

    name    = (c and c["name"]) or ticker
    sector  = (c and c["sector"]) or "—"
    industry= (c and c["industry"]) or "—"
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
        Sector: <span>{sector}</span> &nbsp;·&nbsp;
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
