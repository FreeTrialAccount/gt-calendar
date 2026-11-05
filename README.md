# GT Racing Calendar

Subscribable iCalendar (.ics) feed of select major GT and sportscar racing series + other marquee events.

# Series covered

	24HSeries — Michelin 24H Series
	AsianLMS — Asian Le Mans Series (aka “Winter Le Mans Series”)
	Dakar — Dakar Rally
	DTM — Deutsche Tourenwagen Masters
	ELMS — European Le Mans Series
	GTWCA — GT World Challenge America
	GTWCAsia — GT World Challenge Asia
	GTWCAus — GT World Challenge Australia
	GTWCE — GT World Challenge Europe
	IGTC — Intercontinental GT Challenge
	IMSA — IMSA WeatherTech SportsCar Championship
	IndyCar — NTT IndyCar Series
	Macau — FIA GT World Cup (Macau Grand Prix)
	NASCAR — NASCAR
	NLS — Nürburgring Langstrecken-Serie
	Supercars — Repco Supercars Championship (Enduro Cup and Finals Series events only)
	SuperGT — Super GT
	SuperTaikyu — Super Taikyu Fuji 24 Hours
	WEC — FIA World Endurance Championship

# Files

| File | Purpose |
|------|---------|
| `races.csv` | One row per session — the calendar data |
| `where_to_watch.csv` | Default watch link and notes per series |
| `generate_ics.py` | Builds `gt-racing-calendar.ics` from the two CSVs |
| `.github/workflows/deploy.yml` | Runs the generator and publishes to GitHub Pages |

The `.ics` file is built by GitHub Actions and is not stored in the repo (see `.gitignore`).

# How-to

1. Edit `races.csv` (or `where_to_watch.csv` / `generate_ics.py`)
2. Commit and push to the `main` branch
3. GitHub Actions runs `generate_ics.py`
4. `.ics` file is published to GitHub Pages
5. Phone subscribed calendar updates on its own 

# Subscribe (iPhone)

1. Open **Settings → Calendar → Accounts → Add Account → Other**
2. Tap **Add Subscribed Calendar**
3. Enter: `https://FreeTrialAccount.github.io/gt-calendar/gt-racing-calendar.ics`
4. Save

# CSV format

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| series | Yes | Series short code | `WEC`, `IMSA`, `DTM` |
| event_name | Yes | Race/event name | `24 Hours of Le Mans` |
| circuit | Yes | Track name | `Circuit de la Sarthe` |
| location | No | City, country | `Le Mans, France` |
| date_start | Yes | Start date (M/D/YYYY; YYYY-MM-DD also accepted) | `6/13/2026` |
| date_end | Yes | End date, same format | `6/14/2026` |
| time_start | No | Start time, track-local 24h | `16:00` |
| time_end | No | End time, track-local 24h | `16:00` |
| duration | No | Session length; sets the end time when `time_end` is blank | `24h`, `2h40min`, `~75min`, `250km`, `500mi`, `Sprint` |
| session_type | No | Session kind | `Race`, `Qualifying` |
| timezone | Yes* | IANA zone of the track | `Europe/Paris` |
| notes | No | Free text; no URLs, and don't repeat other columns | `Season finale` |
| status | No | `CONFIRMED`, `TENTATIVE` or `CANCELLED` | `TENTATIVE` |
| watch_url | No | Watch link for this row only; overrides the series link in `where_to_watch.csv` | `https://…/watch-live` |
| drivers | No | Drivers of interest, separated by `;` | `Max Verstappen` |

\*Required when `time_start` is set. Timed events are converted to UTC in the feed, so they show in your phone's local time. Rows without `time_start` become all-day events spanning `date_start`–`date_end`, with `(TBA)` in the title.

Notes on the columns:

- **duration** — `~` marks an approximate length; the number after it is still used. Distances become a rough length (≤300 km → 2h, ≤500 km → 3h, longer → 4h); blank or `Sprint` → 1h.
- **status** — `TENTATIVE` is for provisional calendars or an unannounced race day. Past rows are left blank. `CANCELLED` rows stay in the feed with `(CANCELLED)` in the title.
- **Event identity** — `series` + `event_name` + `date_start` together form each event's calendar ID. Keep that combination unique; changing any of the three replaces the event on subscribed phones.
- The event description shows duration, session, track timezone, notes, drivers and the watch link.

# where_to_watch.csv format

| Column | Description | Example |
|--------|-------------|---------|
| series | Series short code, matching `races.csv` | `IMSA` |
| watch_url | Default watch link for every row of the series | `https://www.imsa.com/tvlive/` |
| watch_notes | Added to every event description of the series | `VPN required` |

This file is optional; if it is missing, events are built without series watch links.
