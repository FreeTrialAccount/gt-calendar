"""
GT Racing Calendar Generator
Reads races.csv and produces gt-racing-calendar.ics
"""

import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256

# ── Constants ────────────────────────────────────────────────────────────────

CALENDAR_NAME = "GT Racing Calendar 2026"
CALENDAR_DESCRIPTION = "Major GT and sportscar racing series worldwide"
TIMEZONE = "UTC"
OUTPUT_FILE = "gt-racing-calendar.ics"
INPUT_FILE = "races.csv"

# Emoji/prefix per series for easy scanning on your phone
SERIES_PREFIX = {
    "WEC": "🏁 WEC",
    "IMSA": "🇺🇸 IMSA",
    "DTM": "🇩🇪 DTM",
    "GTWCE": "🇪🇺 GTWCE",
    "SuperGT": "🇯🇵 SGT",
    "GTWCA": "🌎 GTWCA",
    "BritishGT": "🇬🇧 BGT",
    "GTAmerica": "🏎️ GTA",
    "GTWCAsia": "🌏 GTWC Asia",
}

# Color coding for series (Apple Calendar supports these)
# Values: https://www.kanzaki.com/docs/ical/color.html
SERIES_COLOR = {
    "WEC": "#534AB7",
    "IMSA": "#185FA5",
    "DTM": "#D85A30",
    "GTWCE": "#1D9E75",
    "SuperGT": "#D4537E",
    "GTWCA": "#1D9E75",
    "BritishGT": "#BA7517",
    "GTAmerica": "#BA7517",
    "GTWCAsia": "#1D9E75",
}


# ── Duration Parsing ─────────────────────────────────────────────────────────


def parse_duration(duration_str: str) -> timedelta:
    """Convert human-readable duration to timedelta.

    Supports formats like: 24h, 6h, 100min, 2h40min, 300km, Sprint, TBD
    For distance-based or unknown durations, returns a sensible default.
    """
    s = duration_str.strip().lower()

    if not s or s in ("tbd", "sprint"):
        return timedelta(hours=2)  # Default for sprints / unknown

    # Match "2h40min" or "2h" or "100min"
    match = re.match(r"(?:(\d+)h)?(?:(\d+)min)?$", s)
    if match and (match.group(1) or match.group(2)):
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return timedelta(hours=hours, minutes=minutes)

    # Distance-based (300km, 500km) → estimate
    km_match = re.match(r"(\d+)km$", s)
    if km_match:
        km = int(km_match.group(1))
        if km <= 300:
            return timedelta(hours=2)
        elif km <= 500:
            return timedelta(hours=3)
        else:
            return timedelta(hours=4)

    return timedelta(hours=2)  # Fallback


# ── ICS Building ──────────────────────────────────────────────────────────────


def make_uid(row: dict) -> str:
    """Generate a stable, unique ID for each event."""
    key = f"{row['series']}-{row['event_name']}-{row['date_start']}"
    return sha256(key.encode()).hexdigest()[:16] + "@gt-calendar"


def escape_ics(text: str) -> str:
    """Escape special characters per RFC 5545."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def fold_line(line: str) -> str:
    """Fold long lines at 75 octets per RFC 5545."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    result = []
    while len(encoded) > 75:
        # Find a safe split point (don't break multi-byte chars)
        cut = 75 if not result else 74  # subsequent lines have leading space
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        if result:
            result.append(" " + encoded[:cut].decode("utf-8"))
        else:
            result.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    if encoded:
        result.append(" " + encoded.decode("utf-8"))
    return "\r\n".join(result)


def build_event(row: dict) -> str:
    """Build a single VEVENT block from a CSV row."""
    series = row["series"].strip()
    prefix = SERIES_PREFIX.get(series, series)
    summary = f"{prefix} | {row['event_name'].strip()}"
    location = row.get("circuit", "").strip()
    if row.get("location", "").strip():
        location += f", {row['location'].strip()}"

    dt_start = datetime.strptime(row["date_start"].strip(), "%Y-%m-%d")
    dt_end = datetime.strptime(row["date_end"].strip(), "%Y-%m-%d")
    duration = parse_duration(row.get("duration", ""))

    # If single-day event, use start time + duration
    # If multi-day (like Le Mans or Spa 24h), span the full date range
    if dt_start == dt_end:
        # All-day event with duration in description
        dtstart_str = dt_start.strftime("%Y%m%d")
        dtend_str = (dt_end + timedelta(days=1)).strftime("%Y%m%d")
        use_allday = True
    else:
        dtstart_str = dt_start.strftime("%Y%m%d")
        dtend_str = (dt_end + timedelta(days=1)).strftime("%Y%m%d")
        use_allday = True

    notes_parts = []
    if row.get("duration", "").strip():
        notes_parts.append(f"Duration: {row['duration'].strip()}")
    if row.get("session_type", "").strip():
        notes_parts.append(f"Session: {row['session_type'].strip()}")
    if row.get("notes", "").strip():
        notes_parts.append(row["notes"].strip())
    description = " | ".join(notes_parts)

    uid = make_uid(row)
    now = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
    ]

    if use_allday:
        lines.append(f"DTSTART;VALUE=DATE:{dtstart_str}")
        lines.append(f"DTEND;VALUE=DATE:{dtend_str}")
    else:
        lines.append(f"DTSTART:{dtstart_str}")
        lines.append(f"DTEND:{dtend_str}")

    lines.extend([
        f"SUMMARY:{escape_ics(summary)}",
        f"LOCATION:{escape_ics(location)}",
        f"DESCRIPTION:{escape_ics(description)}",
        f"CATEGORIES:{escape_ics(series)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

    return "\r\n".join(fold_line(line) for line in lines)


def build_calendar(events: list[str]) -> str:
    """Wrap events in a VCALENDAR container."""
    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GT Racing Calendar//EN",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        f"X-WR-CALDESC:{CALENDAR_DESCRIPTION}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-TIMEZONE:UTC",
    ])
    footer = "END:VCALENDAR"
    return header + "\r\n" + "\r\n".join(events) + "\r\n" + footer + "\r\n"


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    csv_path = Path(__file__).parent / INPUT_FILE
    out_path = Path(__file__).parent / OUTPUT_FILE

    if not csv_path.exists():
        print(f"ERROR: {INPUT_FILE} not found in {csv_path.parent}")
        sys.exit(1)

    events = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # line 2 = first data row
            try:
                events.append(build_event(row))
            except Exception as e:
                print(f"WARNING: Skipping row {i} ({row.get('event_name', '???')}): {e}")

    calendar = build_calendar(events)
    out_path.write_text(calendar, encoding="utf-8")

    print(f"Generated {OUTPUT_FILE} with {len(events)} events")


if __name__ == "__main__":
    main()
