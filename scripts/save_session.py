"""
Saves the most recent Claude Code session for this project as a readable
markdown file in planning/sessions/YYYY-MM-DD-HH-MM.md.

Run manually at end of session, or triggered automatically via Stop hook
in .claude/settings.json:

    "hooks": {
        "Stop": [{"matcher": "", "hooks": [{"type": "command",
            "command": "python3 /Users/jessekilburn/projects/trader/scripts/save_session.py"}]}]
    }

Usage:
    python3 scripts/save_session.py            # save most recent session
    python3 scripts/save_session.py --all      # save all unsaved sessions
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

PROJECT_DIR  = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_DIR / "planning" / "sessions"
TRANSCRIPTS  = Path.home() / ".claude" / "projects" / "-Users-jessekilburn-projects-trader"


def extract_messages(jsonl_path: Path) -> list[dict]:
    messages = []
    for line in jsonl_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = obj.get("type")
        if role not in ("user", "assistant"):
            continue
        if obj.get("isSidechain"):
            continue

        msg     = obj.get("message", {})
        content = msg.get("content", "")
        text    = ""

        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    parts.append(block.get("text", "").strip())
                elif block.get("type") == "tool_use":
                    name  = block.get("name", "tool")
                    inp   = block.get("input", {})
                    # show a compact summary, not raw JSON
                    if name == "Bash":
                        parts.append(f"_`{inp.get('command','')[:120]}`_")
                    elif name in ("Read", "Edit", "Write", "Glob", "Grep"):
                        path = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
                        parts.append(f"_[{name}: {path}]_")
                    else:
                        parts.append(f"_[{name}]_")
                elif block.get("type") == "tool_result":
                    # skip tool result blocks — they're noise in a summary
                    pass
            text = "\n\n".join(p for p in parts if p)

        if text:
            messages.append({"role": role, "text": text})

    return messages


def session_to_markdown(jsonl_path: Path) -> str:
    mtime    = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
    date_str = mtime.strftime("%Y-%m-%d %H:%M UTC")
    stem     = jsonl_path.stem[:8]  # first 8 chars of session UUID

    messages = extract_messages(jsonl_path)

    lines = [
        f"# Session — {date_str}",
        f"",
        f"Session ID: `{jsonl_path.stem}`  ",
        f"Messages: {len(messages)}  ",
        f"Saved: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
    ]

    for msg in messages:
        if msg["role"] == "user":
            lines.append(f"**You:** {msg['text']}")
        else:
            lines.append(f"**Pythia:** {msg['text']}")
        lines.append("")

    return "\n".join(lines)


def already_saved(session_id: str) -> bool:
    return any(SESSIONS_DIR.glob(f"*{session_id[:8]}*"))


def save_session(jsonl_path: Path, force: bool = False) -> Path | None:
    if not force and already_saved(jsonl_path.stem):
        return None

    mtime    = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
    filename = mtime.strftime(f"%Y-%m-%d-%H%M-{jsonl_path.stem[:8]}.md")
    out_path = SESSIONS_DIR / filename

    md = session_to_markdown(jsonl_path)
    out_path.write_text(md)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Save Claude Code session transcripts as markdown")
    parser.add_argument("--all",   action="store_true", help="Save all unsaved sessions")
    parser.add_argument("--force", action="store_true", help="Re-save even if already saved")
    args = parser.parse_args()

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_files = sorted(TRANSCRIPTS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not jsonl_files:
        print("No session files found.")
        sys.exit(0)

    targets = jsonl_files if args.all else [jsonl_files[0]]
    saved   = 0

    for f in targets:
        out = save_session(f, force=args.force)
        if out:
            print(f"  Saved → {out.relative_to(PROJECT_DIR)}")
            saved += 1
        else:
            print(f"  Skipped {f.stem[:8]} — already saved (use --force to overwrite)")

    if saved == 0:
        print("Nothing new to save.")
    else:
        print(f"\n{saved} session(s) saved to planning/sessions/")


if __name__ == "__main__":
    main()
