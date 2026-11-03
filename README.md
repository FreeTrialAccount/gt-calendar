# GT Racing Calendar

Subscribable iCalendar (.ics) feed of major GT and sportscar racing series.

# Series covered

    WEC — FIA World Endurance Championship
    IMSA — IMSA WeatherTech SportsCar Championship
    DTM — Deutsche Tourenwagen Masters
    GTWCE — GT World Challenge Europe
    SuperGT — Super GT (Japan)
    GTWCA — GT World Challenge America
    GTWCAsia — GT World Challenge Asia
    GTAmerica — GT America Series
    IGTC — Intercontinental GT Challenge
    24HSeries — Michelin 24H Series
    NLS — Nürburgring Langstrecken-Serie
    Macau — FIA GT World Cup (Macau Grand Prix)
    GTWCAus — GT World Challenge Australia
    Supercars — Repco Supercars Championship
    

# How-to

1. Edit `races.csv`
2. Commit and push to GitHub
3. GitHub Actions runs `generate_ics.py` automatically
4. The `.ics` file is published to GitHub Pages
5. Your phone's subscribed calendar updates on its own

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
| date_start | Yes | Start date (M/D/YYYY or YYYY-MM-DD) | `6/13/2026` |
| date_end | Yes | End date (M/D/YYYY or YYYY-MM-DD) | `6/14/2026` |
| time_start | No | Start time, track-local 24h | `16:00` |
| time_end | No | End time, track-local 24h | `16:00` |
| duration | No | Race length; sets end time when `time_end` is blank | `24h`, `6h`, `100min`, `300km`, `Sprint` |
| session_type | No | Event type | `Race`, `Qualifying`, `Test` |
| timezone | Yes* | IANA zone of the track | `Europe/Paris` |
| notes | No | Free text | `Season finale` |

\*Required when `time_start` is set. Timed events are converted to UTC in the feed, so they show in your phone's local time. Rows without `time_start` become all-day events with `(TBA)` in the title.
