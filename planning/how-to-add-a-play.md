# How to Add a Play

Plays are curated thematic investment ideas. Each play has a thesis and a list of associated tickers.

## Steps

1. Open `scripts/plays_data.py`
2. Add a new dict to the `PLAYS` list:

```python
{
    "id": "url-safe-slug",           # used as the filename, e.g. "ai-infrastructure"
    "title": "Display Name",
    "status": "active",              # "active" | "watch" | "closed"
    "summary": "One-line description for the index table.",
    "thesis": "Full rationale paragraph(s) shown on the play detail page.",
    "tickers": ["AAPL", "MSFT"],     # must exist in the database
    "added": "2026-04-18",           # ISO date
},
```

3. Make sure any tickers listed are in the database. If not, run:

```bash
python3 scripts/refresh.py TICKER
python3 scripts/screen.py
```

4. Rebuild the site:

```bash
python3 scripts/build_site.py
```

5. Commit and push:

```bash
git add docs/ scripts/plays_data.py
git commit -m "Add play: Display Name"
git push
```

## Status values

| Status | Badge | Meaning |
|--------|-------|---------|
| `active` | Green / Buy | Conviction idea, ready to act on |
| `watch` | Amber / Watch | Promising but a condition must be met first |
| `closed` | Grey / Pass | Thesis played out or invalidated |

## Notes

- Tickers in a play link to their company profile pages (`docs/profiles/TICKER.html`)
- Tier and score shown on the play detail page come from the most recent screener run
- To update an existing play, edit its dict in `plays_data.py` and rebuild
- The plays index (`docs/plays.html`) and all detail pages are regenerated on every build
