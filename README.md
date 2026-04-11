# GT Racing Calendar

Subscribable iCalendar (.ics) feed of major GT and sportscar racing series.

# Series covered

- WEC – FIA World Endurance Championship
- IMSA – IMSA WeatherTech SportsCar Championship
- DTM – Deutsche Tourenwagen Masters
- GTWCE – GT World Challenge Europe
- SuperGT – Super GT


# How it works

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
| date_start | Yes | Start date (YYYY-MM-DD) | `2026-06-13` |
| date_end | Yes | End date (YYYY-MM-DD) | `2026-06-14` |
| duration | No | Race length | `24h`, `6h`, `100min`, `300km`, `Sprint` |
| session_type | No | Event type | `Race`, `Qualifying`, `Test` |
| notes | No | Free text | `Season finale` |
