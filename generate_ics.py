"""
GT Racing Calendar Generator
Reads races.csv (+ optional where_to_watch.csv) and produces gt-racing-calendar.ics

Events with time_start + timezone → track-local time converted to UTC (DTSTART:...Z)
Events without times → all-day DATE events with " (TBA)" appended to the title
status column → STATUS (CONFIRMED / TENTATIVE / CANCELLED); cancelled also flagged in title
Watch link → row watch_url, else the series' watch_url from where_to_watch.csv
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

CALENDAR_NAME = "GT Racing Calendar"
CALENDAR_DESCRIPTION = "Major GT and sportscar racing series plus selected marquee events"
OUTPUT_FILE = "gt-racing-calendar.ics"
INPUT_FILE = "races.csv"
WATCH_FILE = "where_to_watch.csv"  # optional per-series lookup: series,watch_url,watch_notes

VALID_STATUS = {"CONFIRMED", "TENTATIVE", "CANCELLED"}  # RFC 5545 VEVENT STATUS values

# Emoji/prefix per series for easy scanning on your phone
SERIES_PREFIX = {
    "WEC": "🌍 WEC",
    "IMSA": "🌎 IMSA",
    "DTM": "🇩🇪 DTM",
    "GTWCE": "🇪🇺 GTWCE",
    "SuperGT": "🇯🇵 SGT",
    "GTWCA": "🦅 GTWCA",  
    "GTAmerica": "🇺🇸 GTA",
    "GTWCAsia": "🐉 GTWC Asia",
    "IGTC": "🌍 IGTC",
    "24HSeries": "🇪🇺 24H",
    "NLS": "🇩🇪 NLS",
    "Macau": "🇲🇴 Macau",
    "GTWCAus": "🐨 GTWC Aus",
    "Supercars": "🇦🇺 SC",
    "AsianLMS": "🌏 AsLMS",
    "ELMS": "🇪🇺 ELMS",
    "SuperTaikyu": "🗻 S-Tai",
    "Dakar": "🏁 Dakar",
    "NASCAR": "🍺 NASCAR",
    "IndyCar": "🏎️ IndyCar",
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def g(row: dict, key: str) -> str:
    """Safely get a CSV field, returning '' if missing or None."""
    val = row.get(key)
    return val.strip() if val else ""


def load_watch_lookup(path: Path) -> dict[str, dict]:
    """Read the per-series watch table. Missing file → empty lookup (not fatal)."""
    if not path.exists():
        print(f"NOTE: {path.name} not found; series watch links skipped")
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {g(r, "series"): r for r in csv.DictReader(f) if g(r, "series")}


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

    Supports formats like: 24h, 2.5h, ~75min, 2h40min, 300km, 500mi, Sprint, TBD
    For distance-based or unknown durations, returns a sensible default.
    """
    s = duration_str.strip().lower().lstrip("~")  # "~30min" = approximately 30min

    if not s or s in ("tbd", "sprint"):
        return timedelta(hours=1)

    match = re.match(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+)min)?$", s)
    if match and (match.group(1) or match.group(2)):
        hours = float(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return timedelta(hours=hours, minutes=minutes)

    dist_match = re.match(r"(\d+)(km|mi)$", s)
    if dist_match:
        km = int(dist_match.group(1)) * (1.609 if dist_match.group(2) == "mi" else 1)
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


def to_utc_stamp(local: datetime, tz: ZoneInfo) -> str:
    """Interpret a naive track-local datetime in tz and format it as UTC (…Z).

    zoneinfo applies each zone's real DST rules (EU last-Sunday, southern
    hemisphere, no-DST zones), so no VTIMEZONE blocks are needed.
    """
    return local.replace(tzinfo=tz).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
    while encoded:
        # First line holds 75 octets; continuation lines 74 + the leading space.
        limit = 75 if not result else 74
        cut = len(encoded) if len(encoded) <= limit else limit
        while cut < len(encoded) and cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1  # don't split a multi-byte UTF-8 character
        chunk = encoded[:cut].decode("utf-8")
        result.append(chunk if not result else " " + chunk)
        encoded = encoded[cut:]
    return "\r\n".join(result)


def build_event(row: dict, watch: dict[str, dict]) -> str:
    """Build a single VEVENT block from a CSV row."""
    series = g(row, "series")
    series_watch = watch.get(series, {})
    watch_url = g(row, "watch_url") or g(series_watch, "watch_url")
    watch_notes = g(series_watch, "watch_notes")
    drivers = [d.strip() for d in g(row, "drivers").split(";") if d.strip()]
    status = g(row, "status").upper()
    if status and status not in VALID_STATUS:
        print(f"WARNING: {g(row, 'event_name')}: unknown status {status!r} ignored")
        status = ""
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
    if drivers:
        notes_parts.append(f"Drivers: {', '.join(drivers)}")
    if watch_url:
        notes_parts.append(f"Watch: {watch_url}")
    if watch_notes:
        notes_parts.append(watch_notes)
    description = " | ".join(notes_parts)

    if status == "CANCELLED":
        summary = f"{summary} (CANCELLED)"

    uid = make_uid(row)
    now = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
    ]

    if time_start and tz_id:
        # ── Timed event: track-local time → UTC ──
        tz = ZoneInfo(tz_id)  # unknown zone raises → row skipped with a warning
        start_dt = dt_start.replace(hour=time_start[0], minute=time_start[1])
        lines.append(f"DTSTART:{to_utc_stamp(start_dt, tz)}")

        if time_end:
            end_base = dt_start if dt_start == dt_end else dt_end
            end_dt = end_base.replace(hour=time_end[0], minute=time_end[1])
            if time_end[0] < time_start[0] and dt_start == dt_end:
                end_dt += timedelta(days=1)
            lines.append(f"DTEND:{to_utc_stamp(end_dt, tz)}")
        else:
            # Elapsed duration, added in UTC so a DST change mid-race doesn't skew it
            end_utc = start_dt.replace(tzinfo=tz).astimezone(timezone.utc) + duration
            lines.append(f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}")
    else:
        # ── All-day fallback for TBC times ──
        if status != "CANCELLED":
            summary = f"{summary} (TBA)"
        dtstart_str = dt_start.strftime("%Y%m%d")
        dtend_str = (dt_end + timedelta(days=1)).strftime("%Y%m%d")
        lines.append(f"DTSTART;VALUE=DATE:{dtstart_str}")
        lines.append(f"DTEND;VALUE=DATE:{dtend_str}")

    lines.extend([
        f"SUMMARY:{escape_ics(summary)}",
        f"LOCATION:{escape_ics(location)}",
        f"DESCRIPTION:{escape_ics(description)}",
        f"CATEGORIES:{escape_ics(series)}",
    ])
    if status:
        lines.append(f"STATUS:{status}")
    if watch_url:
        lines.append(f"URL:{watch_url}")  # URI value: not text-escaped
    lines.extend([
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])

    return "\r\n".join(fold_line(line) for line in lines)


def build_calendar(events: list[str]) -> str:
    """Wrap events in a VCALENDAR container (all timed events are UTC)."""
    header = "\r\n".join(fold_line(line) for line in [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GT Racing Calendar//EN",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        f"X-WR-CALDESC:{CALENDAR_DESCRIPTION}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ])

    events_block = "\r\n".join(events)
    footer = "END:VCALENDAR"

    return "\r\n".join([header, events_block, footer]) + "\r\n"


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    csv_path = Path(__file__).parent / INPUT_FILE
    out_path = Path(__file__).parent / OUTPUT_FILE

    if not csv_path.exists():
        print(f"ERROR: {INPUT_FILE} not found in {csv_path.parent}")
        sys.exit(1)

    watch = load_watch_lookup(Path(__file__).parent / WATCH_FILE)
    events = []
    tz_ids_seen: set[str] = set()
    series_seen: set[str] = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            try:
                events.append(build_event(row, watch))
                tz_id = g(row, "timezone")
                if tz_id:
                    tz_ids_seen.add(tz_id)
                series_seen.add(g(row, "series"))
            except Exception as e:
                print(f"WARNING: Skipping row {i} ({g(row, 'event_name')}): {e}")

    for label, missing in (("emoji prefix", series_seen - SERIES_PREFIX.keys()),
                           (WATCH_FILE, series_seen - watch.keys() if watch else set())):
        if missing:
            print(f"NOTE: series without {label}: {', '.join(sorted(missing))}")

    calendar = build_calendar(events)
    out_path.write_text(calendar, encoding="utf-8", newline="")

    allday = sum(1 for e in events if "DTSTART;VALUE=DATE" in e)
    timed = len(events) - allday
    print(f"Generated {OUTPUT_FILE} with {len(events)} events ({timed} timed, {allday} all-day/TBA)")
    print(f"Track timezones (converted to UTC): {', '.join(sorted(tz_ids_seen))}")


if __name__ == "__main__":
    main()