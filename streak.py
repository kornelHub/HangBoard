#!/usr/bin/env python3
"""Recompute streak stats for the Abrahamson hangs log.

Reads ``abrahamson-hangs.md``, parses the monthly calendar tables, and
rewrites the streak counter table in place between the
``<!-- streak:start -->`` and ``<!-- streak:end -->`` markers.

Cell markers in calendar tables (emoji preferred, legacy text accepted):
    ✅  or  [x]   done       -> extends current streak
    💤  or  R     rest       -> neutral (does not break or extend)
    ❌  or  —     skip       -> breaks current streak
    ⬜  or  [ ]   pending    -> for past days: break; today: ignored

Usage::

    python3 streak.py
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "abrahamson-hangs.md"

MONTH_LOOKUP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

CELL_RE = re.compile(
    r"^\s*(\d{1,2})\s*(\[[xX ]\]|R|—|-|✅|💤|❌|⬜)?\s*$"
)
SECTION_RE = re.compile(r"^###\s+(\w+)\s+(\d{4})\s*$", re.MULTILINE)
HEADER_OR_SEP_RE = re.compile(
    r"\|\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun|---|:--)"
)
STREAK_BLOCK_RE = re.compile(
    r"(<!--\s*streak:start\s*-->\n)(.*?)(<!--\s*streak:end\s*-->)",
    re.DOTALL,
)


def parse_calendar(text: str) -> dict[date, str]:
    """Return ``{date: status}`` for every dated cell found.

    Status is one of ``'done'``, ``'rest'``, ``'skip'``, ``'pending'``.
    """
    out: dict[date, str] = {}
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        month_name = m.group(1)
        if month_name not in MONTH_LOOKUP:
            continue
        month = MONTH_LOOKUP[month_name]
        year = int(m.group(2))
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[m.end():end_idx]

        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if HEADER_OR_SEP_RE.match(stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            for cell in cells:
                if not cell:
                    continue
                cm = CELL_RE.match(cell)
                if not cm:
                    continue
                day = int(cm.group(1))
                marker = (cm.group(2) or "").strip()
                try:
                    d = date(year, month, day)
                except ValueError:
                    continue
                if marker.lower() == "[x]" or marker == "✅":
                    out[d] = "done"
                elif marker == "R" or marker == "💤":
                    out[d] = "rest"
                elif marker in ("—", "-", "❌"):
                    out[d] = "skip"
                else:
                    out[d] = "pending"
    return out


def compute_stats(
    statuses: dict[date, str], today: date
) -> tuple[int, int, int]:
    """Return ``(current_streak, longest_streak, total_sessions)``."""
    total = sum(1 for s in statuses.values() if s == "done")

    # Current streak: walk backwards from today. Today may still be
    # pending (hasn't been logged yet) — that doesn't break the streak.
    current = 0
    d = today
    if statuses.get(today) in (None, "pending"):
        d -= timedelta(days=1)
    while d in statuses:
        s = statuses[d]
        if s == "done":
            current += 1
        elif s == "rest":
            pass
        else:
            break
        d -= timedelta(days=1)

    # Longest streak: scan chronologically up to today.
    longest = 0
    run = 0
    if statuses:
        d = min(statuses)
        while d <= today:
            s = statuses.get(d, "pending")
            if s == "done":
                run += 1
                longest = max(longest, run)
            elif s == "rest":
                pass
            elif s == "pending" and d == today:
                pass
            else:
                run = 0
            d += timedelta(days=1)

    return current, longest, total


def update_text(text: str, current: int, longest: int, total: int) -> str:
    def plural(n: int) -> str:
        return "day" if n == 1 else "days"

    block = (
        "| Streak | Value |\n"
        "|---|---|\n"
        f"| Current streak | {current} {plural(current)} |\n"
        f"| Longest streak | {longest} {plural(longest)} |\n"
        f"| Total sessions | {total} |\n"
    )
    new_text, n = STREAK_BLOCK_RE.subn(
        lambda m: f"{m.group(1)}{block}{m.group(3)}", text
    )
    if n == 0:
        sys.exit(
            "ERROR: streak markers not found in "
            f"{LOG_PATH.name}. Expected <!-- streak:start --> ... "
            "<!-- streak:end -->."
        )
    return new_text


def main() -> None:
    text = LOG_PATH.read_text(encoding="utf-8")
    statuses = parse_calendar(text)
    current, longest, total = compute_stats(statuses, date.today())
    new_text = update_text(text, current, longest, total)
    if new_text != text:
        LOG_PATH.write_text(new_text, encoding="utf-8")
        print(f"Updated {LOG_PATH.name}")
    else:
        print(f"No changes to {LOG_PATH.name}")
    word = lambda n: "day" if n == 1 else "days"
    print(f"  Current streak: {current} {word(current)}")
    print(f"  Longest streak: {longest} {word(longest)}")
    print(f"  Total sessions: {total}")


if __name__ == "__main__":
    main()
