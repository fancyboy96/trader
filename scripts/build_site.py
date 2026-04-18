"""
Generates the Pythia static site into docs/.

Pages produced:
  docs/index.html               — screener dashboard
  docs/profiles/TICKER.html     — company profile per ticker in screen_results

Run after refresh.py, news.py, and screen.py:
    python scripts/build_site.py
"""

from pathlib import Path
from datetime import date
from db import get_conn, init_db

DOCS = Path(__file__).parent.parent / "docs"
PROFILES = DOCS / "profiles"


# ── Shared CSS (Pythia design system) ───────────────────────────────────────

CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root { --ease-out: cubic-bezier(0.16,1,0.3,1); --dur: 200ms; }
    :root, [data-theme="light"] {
      --bg:#FFFFFF; --bg-card:#F4F6FA; --bg-row:#EDF0F7; --bg-hover:#E5EAF5;
      --border:#D6DCE8; --accent:#2558C4; --accent-dim:#9BB0D4;
      --text:#0C1A36; --text-dim:#6B7FA0; --green:#16A34A; --red:#DC2626; --blue:#2563EB;
    }
    [data-theme="dark"] {
      --bg:#0A1220; --bg-card:#0D1729; --bg-row:#172036; --bg-hover:#1E2D45;
      --border:#1E2D45; --accent:#F2BDCC; --accent-dim:#7A3D52;
      --text:#F0F4F8; --text-dim:#7A9AB8; --green:#34d399; --red:#f87171; --blue:#60a5fa;
    }
    body { background:var(--bg); color:var(--text);
           font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
           font-size:15px; line-height:1.65; padding:40px 32px;
           max-width:1100px; margin:0 auto;
           transition:background var(--dur) var(--ease-out),color var(--dur) var(--ease-out); }
    a { color:var(--accent); text-decoration:none; }
    a:hover { text-decoration:underline; }
    .report-header { border-bottom:1px solid var(--accent); padding-bottom:20px; margin-bottom:36px; }
    .report-header-row { display:flex; justify-content:space-between; align-items:flex-start; }
    .label { color:var(--accent); font-size:12px; letter-spacing:.15em; text-transform:uppercase; margin-bottom:6px; }
    h1 { font-size:24px; font-weight:normal; letter-spacing:.02em; }
    .meta { color:var(--text-dim); font-size:12px; margin-top:8px; }
    .meta span { color:var(--text-dim); font-weight:600; }
    section { margin-bottom:44px; }
    .section-title { color:var(--accent); font-size:12px; letter-spacing:.15em; text-transform:uppercase;
                     border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:18px; }
    .stat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:8px; }
    .stat-card { background:var(--bg-card); border:1px solid var(--border); padding:16px 18px; }
    .stat-card .stat-label { color:var(--text-dim); font-size:11px; letter-spacing:.1em; text-transform:uppercase; margin-bottom:6px; }
    .stat-card .stat-value { color:var(--accent); font-size:22px; font-weight:bold; }
    .stat-card .stat-value.neutral { color:var(--text); }
    .stat-card .stat-value.green { color:var(--green); }
    .stat-card .stat-value.red { color:var(--red); }
    .stat-card .stat-sub { color:var(--text-dim); font-size:11px; margin-top:4px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    thead th { color:var(--text-dim); font-size:11px; letter-spacing:.08em; text-transform:uppercase;
               text-align:left; padding:6px 10px; border-bottom:1px solid var(--border); }
    thead th.num { text-align:right; }
    tbody tr { border-bottom:1px solid var(--border); }
    tbody tr:nth-child(even) { background:var(--bg-row); }
    tbody tr:hover { background:var(--bg-hover); }
    td { padding:7px 10px; vertical-align:middle; }
    td.num { text-align:right; font-variant-numeric:tabular-nums; }
    td.dim { color:var(--text-dim); }
    td.accent { color:var(--accent); font-weight:600; }
    .badge { display:inline-block; font-size:10px; font-weight:700; letter-spacing:.1em;
             text-transform:uppercase; padding:3px 10px; border-radius:2px; }
    .badge.A { background:#dcfce7; color:#15803d; }
    .badge.B { background:#dbeafe; color:#1d4ed8; }
    .badge.C { background:#fef9c3; color:#854d0e; }
    .badge.D { background:#fee2e2; color:#b91c1c; }
    [data-theme="dark"] .badge.A { background:#14532d; color:#86efac; }
    [data-theme="dark"] .badge.B { background:#1e3a5f; color:#93c5fd; }
    [data-theme="dark"] .badge.C { background:#422006; color:#fde68a; }
    [data-theme="dark"] .badge.D { background:#450a0a; color:#fca5a5; }
    .callout { background:var(--bg-card); border-left:3px solid var(--accent);
               padding:14px 18px; color:var(--text); font-size:14px; line-height:1.75; }
    .callout.blue { border-left-color:var(--blue); }
    .news-item { background:var(--bg-card); border:1px solid var(--border); padding:12px 16px; margin-bottom:8px; }
    .news-item .news-headline { color:var(--text); font-size:13px; margin-bottom:4px; }
    .news-item .news-meta { color:var(--text-dim); font-size:11px; }
    .news-item .news-meta .source { color:var(--accent); }
    .news-item .news-summary { color:var(--text-dim); font-size:12px; margin-top:6px; line-height:1.6; }
    .score-bar-wrap { display:flex; align-items:center; gap:8px; }
    .score-bar { height:6px; background:var(--accent-dim); flex-shrink:0; min-width:2px; }
    .score-bar.fill { background:var(--accent); }
    .theme-toggle { background:transparent; border:1px solid var(--border); border-radius:4px;
                    color:var(--text-dim); font-family:inherit; font-size:10px; font-weight:600;
                    letter-spacing:.08em; text-transform:uppercase; padding:4px 10px; cursor:pointer;
                    transition:border-color var(--dur),color var(--dur); flex-shrink:0; }
    .theme-toggle:hover { border-color:var(--accent); color:var(--accent); }
    .report-footer { border-top:1px solid var(--border); padding-top:16px; margin-top:48px;
                     color:var(--text-dim); font-size:11px; }
    .back-link { font-size:12px; color:var(--text-dim); margin-bottom:24px; display:inline-block; }
    .sub-label { color:var(--text-dim); font-size:10px; letter-spacing:.1em; text-transform:uppercase; margin:20px 0 8px; }
"""

THEME_JS = """
<script>
  function toggleTheme() {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    document.querySelector('.theme-toggle').textContent = next === 'dark' ? 'Light' : 'Dark';
  }
</script>
"""


def html_shell(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Pythia</title>
  <style>{CSS}</style>
</head>
<body>
{body}
{THEME_JS}
</body>
</html>"""


def fmt_large(v) -> str:
    if v is None: return "—"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"


def fmt_pct(v) -> str:
    return f"{v*100:.1f}%" if v is not None else "—"


def fmt_x(v) -> str:
    return f"{v:.1f}x" if v is not None else "—"


def fmt_num(v, dp=2) -> str:
    return f"{v:,.{dp}f}" if v is not None else "—"


# ── Index page ───────────────────────────────────────────────────────────────

def build_index(conn):
    today = date.today().isoformat()

    results = conn.execute("""
        SELECT sr.*, c.name, c.sector, c.industry, f.market_cap, f.revenue_ttm,
               f.fwd_pe, f.gross_margin, f.free_cashflow, f.debt_to_equity
        FROM screen_results sr
        LEFT JOIN companies c ON sr.ticker = c.ticker
        LEFT JOIN fundamentals f ON sr.ticker = f.ticker AND f.snapshot_date = (
            SELECT MAX(snapshot_date) FROM fundamentals WHERE ticker = sr.ticker
        )
        WHERE sr.passed_filters = 1
        ORDER BY sr.score DESC
    """).fetchall()

    filtered = conn.execute(
        "SELECT COUNT(*) FROM screen_results WHERE passed_filters = 0"
    ).fetchone()[0]

    tier_counts = {t: 0 for t in "ABCD"}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1

    # Stat grid
    stats = f"""
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-label">Universe</div>
    <div class="stat-value neutral">{len(results) + filtered}</div>
    <div class="stat-sub">tickers screened</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Tier A</div>
    <div class="stat-value green">{tier_counts['A']}</div>
    <div class="stat-sub">strong candidates</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Tier B</div>
    <div class="stat-value neutral">{tier_counts['B']}</div>
    <div class="stat-sub">watch list</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Filtered out</div>
    <div class="stat-value neutral">{filtered}</div>
    <div class="stat-sub">failed hard filters</div>
  </div>
</div>"""

    # Results table
    rows_html = ""
    for r in results:
        score_w = min(int(r["score"]), 100)
        bar = f'<div class="score-bar-wrap"><div class="score-bar fill" style="width:{score_w}px"></div><span>{r["score"]:.0f}</span></div>'
        profile_link = f'<a href="profiles/{r["ticker"]}.html">{r["ticker"]}</a>'
        rows_html += f"""
    <tr>
      <td class="accent">{profile_link}</td>
      <td>{r['name'] or '—'}</td>
      <td class="dim">{r['sector'] or '—'}</td>
      <td><span class="badge {r['tier']}">{r['tier']}</span></td>
      <td class="num">{bar}</td>
      <td class="num dim">{fmt_large(r['market_cap'])}</td>
      <td class="num dim">{fmt_pct(r['revenue_growth_yoy'])}</td>
      <td class="num dim">{fmt_pct(r['gross_margin'])}</td>
      <td class="num dim">{fmt_x(r['fwd_pe'])}</td>
    </tr>"""

    table = f"""
<table>
  <thead>
    <tr>
      <th>Ticker</th>
      <th>Company</th>
      <th>Sector</th>
      <th>Tier</th>
      <th class="num">Score</th>
      <th class="num">Mkt Cap</th>
      <th class="num">Rev Growth</th>
      <th class="num">Gross Margin</th>
      <th class="num">Fwd P/E</th>
    </tr>
  </thead>
  <tbody>{rows_html}
  </tbody>
</table>"""

    empty_note = "" if results else '<p style="color:var(--text-dim);font-size:13px">No results yet. Run <code>screen.py</code> after loading tickers with <code>refresh.py</code>.</p>'

    body = f"""
<header class="report-header">
  <div class="report-header-row">
    <div>
      <div class="label">Pythia — Portfolio Research</div>
      <h1>Screener Dashboard</h1>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">Dark</button>
  </div>
  <div class="meta">Last run: <span>{today}</span> &nbsp;·&nbsp; Criteria: <span>screening-criteria.md</span></div>
</header>

<section>
  <div class="section-title">Overview</div>
  {stats}
</section>

<section>
  <div class="section-title">Results</div>
  {empty_note}{table if results else ''}
</section>

<footer class="report-footer">
  Pythia &nbsp;·&nbsp; Screener Dashboard &nbsp;·&nbsp; {today} &nbsp;·&nbsp; For personal use only
</footer>"""

    path = DOCS / "index.html"
    path.write_text(html_shell("Screener Dashboard", body))
    print(f"  index.html — {len(results)} tickers")


# ── Profile page ─────────────────────────────────────────────────────────────

def build_profile(conn, ticker: str):
    sr = conn.execute(
        "SELECT * FROM screen_results WHERE ticker = ?", (ticker,)
    ).fetchone()

    c = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()

    f = conn.execute("""
        SELECT * FROM fundamentals WHERE ticker = ?
        ORDER BY snapshot_date DESC LIMIT 1
    """, (ticker,)).fetchone()

    prices = conn.execute("""
        SELECT date, close FROM prices WHERE ticker = ?
        ORDER BY date DESC LIMIT 1
    """, (ticker,)).fetchone()

    news_rows = conn.execute("""
        SELECT * FROM news WHERE ticker = ?
        ORDER BY published_at DESC LIMIT 8
    """, (ticker,)).fetchall()

    name = (c and c["name"]) or ticker
    sector = (c and c["sector"]) or "—"
    industry = (c and c["industry"]) or "—"
    description = (c and c["description"]) or ""
    price = prices["close"] if prices else None
    price_date = prices["date"] if prices else "—"

    # Snapshot grid
    snap = f"""
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-label">Price</div>
    <div class="stat-value neutral">${fmt_num(price)}</div>
    <div class="stat-sub">as of {price_date}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Market Cap</div>
    <div class="stat-value neutral" style="font-size:18px">{fmt_large(f and f['market_cap'])}</div>
    <div class="stat-sub">&nbsp;</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Revenue (ttm)</div>
    <div class="stat-value neutral" style="font-size:18px">{fmt_large(f and f['revenue_ttm'])}</div>
    <div class="stat-sub">Rev growth: {fmt_pct(sr and sr['revenue_growth_yoy'])}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Gross Margin</div>
    <div class="stat-value neutral">{fmt_pct(f and f['gross_margin'])}</div>
    <div class="stat-sub">Net margin: {fmt_pct(f and f['net_margin'])}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Fwd P/E</div>
    <div class="stat-value neutral">{fmt_x(f and f['fwd_pe'])}</div>
    <div class="stat-sub">PEG: {fmt_num(f and f['peg_ratio'])}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">FCF (ttm)</div>
    <div class="stat-value neutral" style="font-size:18px">{fmt_large(f and f['free_cashflow'])}</div>
    <div class="stat-sub">D/E: {fmt_num(f and f['debt_to_equity'])}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">ROE</div>
    <div class="stat-value neutral">{fmt_pct(f and f['roe'])}</div>
    <div class="stat-sub">Beta: {fmt_num(f and f['beta'])}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Screen Score</div>
    <div class="stat-value neutral">{(sr and f'{sr["score"]:.0f}') or '—'} <span style="font-size:14px;font-weight:normal">/ 100</span></div>
    <div class="stat-sub">Tier: <span class="badge {sr['tier'] if sr else 'D'}">{(sr and sr['tier']) or '—'}</span></div>
  </div>
</div>"""

    # Score breakdown
    if sr and sr["passed_filters"]:
        breakdown = f"""
<div class="sub-label">Score breakdown</div>
<table>
  <thead><tr><th>Category</th><th class="num">Score</th><th class="num">Max</th></tr></thead>
  <tbody>
    <tr><td>Growth</td><td class="num accent">{sr['score_growth']:.0f}</td><td class="num dim">30</td></tr>
    <tr><td>Profitability</td><td class="num accent">{sr['score_profitability']:.0f}</td><td class="num dim">25</td></tr>
    <tr><td>Valuation</td><td class="num accent">{sr['score_valuation']:.0f}</td><td class="num dim">25</td></tr>
    <tr><td>Balance Sheet</td><td class="num accent">{sr['score_balance_sheet']:.0f}</td><td class="num dim">20</td></tr>
  </tbody>
</table>"""
    else:
        reason = (sr and sr["filter_fail_reason"]) or "unknown"
        breakdown = f'<div class="callout" style="border-left-color:var(--red)">Failed hard filter: {reason}</div>'

    # Description
    desc_html = f'<div class="callout blue" style="margin-top:0">{description[:800]}</div>' if description else ""

    # News
    news_html = ""
    for n in news_rows:
        title = n["title"] or ""
        url   = n["url"] or "#"
        src   = n["source"] or ""
        pub   = (n["published_at"] or "")[:10]
        summ  = n["summary"] or ""
        news_html += f"""
<div class="news-item">
  <div class="news-headline"><a href="{url}" target="_blank" rel="noopener">{title}</a></div>
  <div class="news-meta"><span class="source">{src}</span> &nbsp;·&nbsp; {pub}</div>
  {'<div class="news-summary">' + summ[:200] + '</div>' if summ else ''}
</div>"""

    if not news_html:
        news_html = '<p style="color:var(--text-dim);font-size:13px">No news stored. Run <code>python scripts/news.py ' + ticker + '</code></p>'

    today = date.today().isoformat()
    body = f"""
<a class="back-link" href="../index.html">← Back to dashboard</a>

<header class="report-header">
  <div class="report-header-row">
    <div>
      <div class="label">Pythia — Company Profile</div>
      <h1>{ticker} &mdash; {name}</h1>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">Dark</button>
  </div>
  <div class="meta">
    Sector: <span>{sector}</span> &nbsp;·&nbsp;
    Industry: <span>{industry}</span> &nbsp;·&nbsp;
    Generated: <span>{today}</span>
  </div>
</header>

<section>
  <div class="section-title">Snapshot</div>
  {snap}
  {breakdown}
</section>

{'<section><div class="section-title">About</div>' + desc_html + '</section>' if desc_html else ''}

<section>
  <div class="section-title">Recent News</div>
  {news_html}
</section>

<footer class="report-footer">
  Pythia &nbsp;·&nbsp; {ticker} Profile &nbsp;·&nbsp; {today} &nbsp;·&nbsp; For personal use only
</footer>"""

    path = PROFILES / f"{ticker}.html"
    path.write_text(html_shell(f"{ticker} — {name}", body))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    init_db()
    DOCS.mkdir(exist_ok=True)
    PROFILES.mkdir(exist_ok=True)

    conn = get_conn()
    print("Building Pythia site...")

    build_index(conn)

    tickers = [r["ticker"] for r in conn.execute(
        "SELECT ticker FROM screen_results"
    ).fetchall()]

    for ticker in tickers:
        build_profile(conn, ticker)

    conn.close()
    print(f"  profiles/ — {len(tickers)} pages")
    print(f"Done → docs/")


if __name__ == "__main__":
    main()
