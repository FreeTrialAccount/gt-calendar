"""
GT Racing Calendar Generator
Reads races.csv and produces gt-racing-calendar.ics

Events with time_start + timezone → proper DTSTART;TZID= entries
Events without times → all-day DATE events (fallback for TBC)
Handles both YYYY-MM-DD and M/D/YYYY date formats (Excel compatibility)
"""

import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256
from zoneinfo import ZoneInfo

# ── Constants ────────────────────────────────────────────────────────────────

CALENDAR_NAME = "GT Racing Calendar 2026"
CALENDAR_DESCRIPTION = "Major GT and sportscar racing series worldwide"
OUTPUT_FILE = "gt-racing-calendar.ics"
INPUT_FILE = "races.csv"

# Emoji/prefix per series for easy scanning on your phone
SERIES_PREFIX = {
    "WEC": "🌍 WEC",
    "IMSA": "🌎 IMSA",
    "DTM": "🇩🇪 DTM",
    "GTWCE": "🇪🇺 GTWCE",
    "SuperGT": "🇯🇵 SGT",
    "GTWCA": "🦅 GTWCA",
    "BritishGT": "🇬🇧 BGT",  
    "GTAmerica": "🇺🇸 GTA",
    "GTWCAsia": "🐉 GTWC Asia",
    "IGTC": "🌍 IGTC",
    "24HSeries": "🇪🇺 24H",
    "NLS": "🇩🇪 NLS",
    "Macau": "🇲🇴 Macau",
    "GTWCAustralia": "🇦🇺 GTWC Aus",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def g(row: dict, key: str) -> str:
    """Safely get a CSV field, returning '' if missing or None."""
    val = row.get(key)
    return val.strip() if val else ""


def parse_date(date_str: str) -> datetime:
    """Parse date string in either YYYY-MM-DD or M/D/YYYY format."""
    s = date_str.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


# ── Duration Parsing ─────────────────────────────────────────────────────────


def parse_duration(duration_str: str) -> timedelta:
    """Convert human-readable duration to timedelta.

    Supports formats like: 24h, 6h, 100min, 2h40min, 300km, Sprint, TBD
    For distance-based or unknown durations, returns a sensible default.
    """
    s = duration_str.strip().lower()

    if not s or s in ("tbd", "sprint"):
        return timedelta(hours=1)

    match = re.match(r"(?:(\d+)h)?(?:(\d+)min)?$", s)
    if match and (match.group(1) or match.group(2)):
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return timedelta(hours=hours, minutes=minutes)

    km_match = re.match(r"(\d+)km$", s)
    if km_match:
        km = int(km_match.group(1))
        if km <= 300:
            return timedelta(hours=2)
        elif km <= 500:
            return timedelta(hours=3)
        else:
            return timedelta(hours=4)

    return timedelta(hours=1)


def parse_time(time_str: str) -> tuple[int, int] | None:
    """Parse HH:MM string into (hour, minute) tuple. Returns None if empty/invalid."""
    if not time_str or not time_str.strip():
        return None
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return None
    return None


# ── Timezone Handling ─────────────────────────────────────────────────────────


def get_vtimezone(tz_id: str) -> str:
    """Generate a VTIMEZONE block for the given IANA timezone."""
    try:
        tz = ZoneInfo(tz_id)
    except (KeyError, Exception):
        return ""

    jan = datetime(2026, 1, 15, tzinfo=tz)
    jul = datetime(2026, 7, 15, tzinfo=tz)

    jan_offset = jan.utcoffset()
    jul_offset = jul.utcoffset()
    jan_name = jan.tzname()
    jul_name = jul.tzname()

    def format_offset(td: timedelta) -> str:
        total = int(td.total_seconds())
        sign = "+" if total >= 0 else "-"
        total = abs(total)
        h = total // 3600
        m = (total % 3600) // 60
        return f"{sign}{h:02d}{m:02d}"

    lines = ["BEGIN:VTIMEZONE", f"TZID:{tz_id}"]

    if jan_offset == jul_offset:
        lines.extend([
            "BEGIN:STANDARD",
            "DTSTART:19700101T000000",
            f"TZOFFSETFROM:{format_offset(jan_offset)}",
            f"TZOFFSETTO:{format_offset(jan_offset)}",
            f"TZNAME:{jan_name}",
            "END:STANDARD",
        ])
    else:
        std_offset = min(jan_offset, jul_offset)
        dst_offset = max(jan_offset, jul_offset)
        std_name = jan_name if jan_offset <= jul_offset else jul_name
        dst_name = jul_name if jul_offset >= jan_offset else jan_name

        lines.extend([
            "BEGIN:STANDARD",
            "DTSTART:19701101T020000",
            "RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11",
            f"TZOFFSETFROM:{format_offset(dst_offset)}",
            f"TZOFFSETTO:{format_offset(std_offset)}",
            f"TZNAME:{std_name}",
            "END:STANDARD",
            "BEGIN:DAYLIGHT",
            "DTSTART:19700308T020000",
            "RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3",
            f"TZOFFSETFROM:{format_offset(std_offset)}",
            f"TZOFFSETTO:{format_offset(dst_offset)}",
            f"TZNAME:{dst_name}",
            "END:DAYLIGHT",
        ])

    lines.append("END:VTIMEZONE")
    return "\r\n".join(lines)


# ── ICS Building ──────────────────────────────────────────────────────────────


def make_uid(row: dict) -> str:
    key = f"{g(row, 'series')}-{g(row, 'event_name')}-{g(row, 'date_start')}"
    return sha256(key.encode()).hexdigest()[:16] + "@gt-calendar"


def escape_ics(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def fold_line(line: str) -> str:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    result = []
    while len(encoded) > 75:
        cut = 75 if not result else 74
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
    series = g(row, "series")
    prefix = SERIES_PREFIX.get(series, series)
    summary = f"{prefix} | {g(row, 'event_name')}"
    location = g(row, "circuit")
    if g(row, "location"):
        location += f", {g(row, 'location')}"

    dt_start = parse_date(g(row, "date_start"))
    dt_end = parse_date(g(row, "date_end"))

    time_start = parse_time(g(row, "time_start"))
    time_end = parse_time(g(row, "time_end"))
    tz_id = g(row, "timezone")
    duration = parse_duration(g(row, "duration"))

    # Build description
    notes_parts = []
    if g(row, "duration"):
        notes_parts.append(f"Duration: {g(row, 'duration')}")
    if g(row, "session_type"):
        notes_parts.append(f"Session: {g(row, 'session_type')}")
    if tz_id:
        notes_parts.append(f"Track TZ: {tz_id}")
    if g(row, "notes"):
        notes_parts.append(g(row, "notes"))
    description = " | ".join(notes_parts)

    uid = make_uid(row)
    now = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
    ]

    if time_start and tz_id:
        # ── Timed event with timezone ──
        start_dt = dt_start.replace(hour=time_start[0], minute=time_start[1])
        dtstart_str = start_dt.strftime("%Y%m%dT%H%M%S")
        lines.append(f"DTSTART;TZID={tz_id}:{dtstart_str}")

        if time_end:
            end_base = dt_start if dt_start == dt_end else dt_end
            end_dt = end_base.replace(hour=time_end[0], minute=time_end[1])
            if time_end[0] < time_start[0] and dt_start == dt_end:
                end_dt += timedelta(days=1)
            dtend_str = end_dt.strftime("%Y%m%dT%H%M%S")
            lines.append(f"DTEND;TZID={tz_id}:{dtend_str}")
        else:
            end_dt = start_dt + duration
            dtend_str = end_dt.strftime("%Y%m%dT%H%M%S")
            lines.append(f"DTEND;TZID={tz_id}:{dtend_str}")
    else:
        # ── All-day fallback for TBC times ──
        dtstart_str = dt_start.strftime("%Y%m%d")
        dtend_str = (dt_end + timedelta(days=1)).strftime("%Y%m%d")
        lines.append(f"DTSTART;VALUE=DATE:{dtstart_str}")
        lines.append(f"DTEND;VALUE=DATE:{dtend_str}")

    lines.extend([
        f"SUMMARY:{escape_ics(summary)}",
        f"LOCATION:{escape_ics(location)}",
        f"DESCRIPTION:{escape_ics(description)}",
        f"CATEGORIES:{escape_ics(series)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

    return "\r\n".join(fold_line(line) for line in lines)


def build_calendar(events: list[str], timezones: list[str]) -> str:
    """Wrap events in a VCALENDAR container with VTIMEZONE blocks."""
    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GT Racing Calendar//EN",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        f"X-WR-CALDESC:{CALENDAR_DESCRIPTION}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ])

    tz_block = "\r\n".join(timezones) if timezones else ""
    events_block = "\r\n".join(events)
    footer = "END:VCALENDAR"

    parts = [header]
    if tz_block:
        parts.append(tz_block)
    parts.append(events_block)
    parts.append(footer)

    return "\r\n".join(parts) + "\r\n"


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    csv_path = Path(__file__).parent / INPUT_FILE
    out_path = Path(__file__).parent / OUTPUT_FILE

    if not csv_path.exists():
        print(f"ERROR: {INPUT_FILE} not found in {csv_path.parent}")
        sys.exit(1)

    events = []
    tz_ids_seen: set[str] = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            try:
                events.append(build_event(row))
                tz_id = g(row, "timezone")
                if tz_id:
                    tz_ids_seen.add(tz_id)
            except Exception as e:
                print(f"WARNING: Skipping row {i} ({g(row, 'event_name')}): {e}")

    # Generate VTIMEZONE blocks for all referenced timezones
    tz_blocks = []
    for tz_id in sorted(tz_ids_seen):
        block = get_vtimezone(tz_id)
        if block:
            tz_blocks.append(block)

    calendar = build_calendar(events, tz_blocks)
    out_path.write_text(calendar, encoding="utf-8")

    timed = sum(1 for e in events if "TZID=" in e)
    allday = len(events) - timed
    print(f"Generated {OUTPUT_FILE} with {len(events)} events ({timed} timed, {allday} all-day)")
    print(f"Timezones included: {', '.join(sorted(tz_ids_seen))}")


if __name__ == "__main__":
    main()
