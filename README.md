<div align="center">

# OddsHarvester

### Scrape sports betting odds from OddsPortal.com with ease

Extract upcoming & historical odds, plus community predictions, tipster profiles and per-match votes, across 11 sports, 100+ leagues, and dozens of betting markets.
<br>Powered by Playwright browser automation. Output to JSON, CSV, or S3.

<br>

[![PyPI version](https://img.shields.io/pypi/v/oddsharvester.svg?style=flat-square)](https://pypi.org/project/oddsharvester/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/github/actions/workflow/status/jordantete/OddsHarvester/run_unit_tests.yml?style=flat-square&label=tests)](https://github.com/jordantete/OddsHarvester/actions)
[![codecov](https://img.shields.io/codecov/c/github/jordantete/OddsHarvester?style=flat-square&token=DOZRQAXAK7)](https://codecov.io/github/jordantete/OddsHarvester)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)

</div>

---

## Quick Start

```bash
# Install
pip install oddsharvester

# Or clone & setup with uv
git clone https://github.com/jordantete/OddsHarvester.git && cd OddsHarvester
pip install uv && uv sync

# Scrape today's upcoming football matches
oddsharvester upcoming -s football -d $(date +%Y%m%d) -m 1x2 --headless

# Scrape historical Premier League odds
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2 --headless

# Snapshot odds for matches in play right now
oddsharvester live -s tennis -m match_winner --headless

# Scrape community data (top predictions here; also --user profiles and --match-url votes)
oddsharvester community -s football --headless
```

---

## Features

|                  | Feature                 | Description                                                                |
| ---------------- | ----------------------- | -------------------------------------------------------------------------- |
| **Upcoming**     | Scrape upcoming matches | Fetch odds and event details for upcoming sports matches by date or league |
| **Historic**     | Scrape historical odds  | Retrieve past odds and match results for any season                        |
| **Live**         | Snapshot in-play odds   | One-shot capture of matches in play, with live score, period and scrape timestamp |
| **Community**    | Scrape community data   | Top predictions, tipster profiles (stats + picks), and per-match community votes |
| **Team**         | Scrape team metadata    | Identity, venue, coach and recent form for a team id, with the name used in match lists |
| **Multi-market** | Advanced parsing        | Structured data: dates, teams, scores, venues, and per-bookmaker odds      |
| **Blocked odds** | Detect pulled markets   | Flags which outcomes a bookmaker has stopped offering (struck-through odds) |
| **Storage**      | Flexible output         | JSON, CSV (local), or direct upload to AWS S3                              |
| **Docker**       | Container-ready         | Run seamlessly in Docker with environment variable configuration           |
| **Proxy**        | Proxy support           | Route through SOCKS/HTTP proxies for geolocation and anti-blocking         |

---

## Supported Sports & Markets

| Sport                | Markets                                                                                        |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| ⚽ Football          | `1x2` `btts` `double_chance` `draw_no_bet` `over/under` `european_handicap` `asian_handicap`   |
| 🎾 Tennis            | `match_winner` `total_sets_over/under` `total_games_over/under` `asian_handicap` `correct_score` |
| 🏀 Basketball        | `1x2` `moneyline` `asian_handicap` `over/under`                                                |
| 🏉 Rugby League      | `1x2` `home_away` `double_chance` `draw_no_bet` `over/under` `handicap`                        |
| 🏉 Rugby Union       | `1x2` `home_away` `double_chance` `draw_no_bet` `over/under` `handicap`                        |
| 🏒 Ice Hockey        | `1x2` `home_away` `double_chance` `draw_no_bet` `btts` `over/under`                            |
| ⚾ Baseball          | `moneyline` `over/under`                                                                       |
| 🏈 American Football | `1x2` `moneyline` `over/under` `asian_handicap`                                                |
| 🤾 Handball          | `1x2` `home_away` `double_chance` `draw_no_bet` `over/under` `handicap`                        |
| 🏐 Volleyball        | `home_away` `total_sets_over/under` `total_points_over/under` `asian_handicap` `correct_score` |
| 🏏 Cricket           | `home_away`                                                                                    |

> **Umbrella tokens (football):** `over_under` and `asian_handicap` are umbrella market tokens — pass either as `--market` and it expands at scrape time to every line OddsPortal actually renders for that match (e.g. `over_under_1_5_market`, `over_under_2_5_market`, …), instead of listing each line by hand.

> **Tennis and volleyball lines:** OddsPortal prints no `Sets`, `Games` or `Points` word on a line, and each axis's ladder can show any value in its range, so a line whose value falls within the other axis's range cannot be told apart on the page. Refused: every tennis sets Asian Handicap line; tennis games AH `-2.5` and `+2.5`; tennis O/U sets and games from `6.5` to `10.5`, whole games lines `7` to `10` included; volleyball sets and points AH `-2.5`, `-1.5`, `+1.5`, `+2.5`. They come back empty with a warning naming the other axis.

> **Cricket:** the scraper supports one cricket market, `home_away` (a 2-way match winner, no draw), over one period, `full_including_ot`: the only ones OddsPortal shows on limited-overs matches (gotchas §14). Since the 2026-08 redesign the match pages carry a per-bookmaker odds table, read like any other sport's.

100+ leagues supported across all sports: Premier League, La Liga, Serie A, NBA, NFL, MLB, NHL, ATP/WTA Grand Slams, and [many more](src/oddsharvester/utils/sport_league_constants.py).

---

## CLI Usage

OddsHarvester has five commands: **`upcoming`**, **`historic`**, **`live`**, **`community`** and **`team`**. The [CLI Options Reference](#cli-options-reference) gives, for each option, the commands that take it.

### `oddsharvester upcoming`

Scrape odds for upcoming matches — by date, by league, or by specific match URL.

```bash
# By date (today here)
oddsharvester upcoming -s football -d $(date +%Y%m%d) -m 1x2 --headless

# By league (scrapes all upcoming matches for that league)
oddsharvester upcoming -s football -l england-premier-league -m 1x2,btts --headless

# Multiple leagues
oddsharvester upcoming -s football -l england-premier-league,spain-laliga -m 1x2 --headless

# Specific match URLs (repeat the flag; works for past matches too)
oddsharvester upcoming -s football --match-link "https://www.oddsportal.com/football/..." -m 1x2

# Preview mode (faster — best/highest odds only, no individual bookmakers)
oddsharvester upcoming -s football -d $(date +%Y%m%d) -m over_under --preview-only --headless

# Only matches kicking off within the next 6 hours (fewer requests)
oddsharvester upcoming -s football -l england-premier-league -m 1x2 --kickoff-within-hours 6 --headless

# Collect links plus kickoff only (fixture plan; no odds scraped)
oddsharvester upcoming -s football -d $(date +%Y%m%d) --links-only -f csv -o upcoming_links.csv
```

### `oddsharvester historic`

Scrape historical odds and results for past seasons.

```bash
# Single league & season
oddsharvester historic -s football -l england-premier-league --season 2022-2023 -m 1x2 --headless

# Current season
oddsharvester historic -s football -l england-premier-league --season current -m 1x2 --headless

# Limit pagination
oddsharvester historic -s football -l england-premier-league --season 2022-2023 -m 1x2 --max-pages 3 --headless

# Output as CSV
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2 -f csv -o premier_league_odds --headless

# Umbrella market — expands to every Over/Under line rendered on the page
oddsharvester historic -s football -l england-premier-league --season 2023-2024 --market over_under -f csv
```

### `oddsharvester live`

Take a one-shot snapshot of matches currently in play, with per-bookmaker in-play odds.

```bash
# Every live match for a sport
oddsharvester live -s tennis -m match_winner --headless

# Restricted to one league
oddsharvester live -s football -l england-premier-league -m 1x2 --headless

# Re-sample one known match without reloading the listing
oddsharvester live -s football --match-link "https://www.oddsportal.com/football/..." -m 1x2 --headless

# Collect live match links only
oddsharvester live -s football --links-only -o live_links.json --headless
```

Each record carries the usual match metadata plus live context: `live_period`
(the period marker exactly as the site displays it, so it is sport-specific:
`4'` or `Half-time` in football, `1st Set` in tennis, `9th Inning` in baseball), `live_score_home`,
`live_score_away`, `live_score_raw` (keeps compound formats such as
`0:1 (3:6, 4:2)`), and `scraped_at_utc`, which is what makes a series of
snapshots comparable.

Notes:

- **Zero live matches is a normal outcome**: the command prints a message and
  exits 0 without writing a file. `upcoming` and `historic` exit 1 on a run that
  scraped no match at all, an empty listing included.
- **Matches that end between listing and scrape are dropped**, so a snapshot only
  ever contains genuinely live matches.
- **In-play bookmaker coverage is thinner than pre-match** (often 2 to 4
  bookmakers instead of 15 to 20) and varies by region.
- `--odds-history` is rejected, and `--period` accepts only the sport's
  full-match period (`full_time`, or `full_including_ot` where that is the
  default), which changes nothing: the in-play view has no history and no
  period selector.
- **For repeated sampling, schedule the command externally** (cron or similar).
  Keep at least 60 seconds between snapshots, and prefer `--match-link` to
  re-sample a known match without re-reading the listing. The command itself
  never refreshes a page, which keeps its request profile identical to
  `upcoming`.

### `oddsharvester community`

Scrape OddsPortal Community data. `community` has three mutually-exclusive modes; exactly one is required:

- **Top predictions** (`--sport`): the most-voted community picks for the next 7 days.
- **User profile** (`--user <username>`): a tipster's stats, monthly performance and recent predictions.
- **Match community votes** (`--match-url <url>`): the community vote split of one match, for the market its page shows on load.

#### Top predictions (`--sport`)

```bash
# Top predictions for a sport
oddsharvester community -s football --headless

# Write to a named JSON file
oddsharvester community -s football -f json -o top_predictions.json --headless
```

Each record contains the match (`home_team`, `away_team`, `match_url`, `kickoff` as `YYYY-MM-DDTHH:MM` in the browser timezone (`--timezone`), plus the raw `kickoff_text` label kept as fallback when the date token fails to parse), the league (`sport`, `country`, `league`), the voted `market`, best odds per outcome (`odds`), the community vote split (`community_votes_pct`), and `scraped_at`.

- OddsPortal surfaces ~10 picks per sport (no pagination) with rounded percentages.

#### User profile (`--user <username>`)

```bash
oddsharvester community --user BLAPRO --headless
```

Emits one record: `mode` (`"user"`), the header (`username`, `roi_pct`, `member_since`,
`country`, `privacy`), the monthly `statistics` table (`month`, `total_predictions`, `won`,
`lost`, `plus_minus`, `roi_pct`, incl. a `Total` row), the rendered `predictions` batch and
`scraped_at`. Each prediction has `kickoff` (`YYYY-MM-DDTHH:MM` in the browser timezone) with
the raw `kickoff_text` kept as fallback, `market`, `home_team`/`away_team`, `score` (when
finished), `match_url`, and a positional `outcomes` list of `{odds, community_pct, picked}`
plus `pick_odds`. Most profiles are **private**: a private
profile returns the header only (`privacy: "private"`, empty stats/predictions) and exits 0.

#### Match community votes (`--match-url <url>`)

```bash
oddsharvester community --match-url "https://www.oddsportal.com/football/h2h/.../" --headless
```

Emits one record: `mode` (`"match"`), `match_url`, `event_id` (the id after the URL's `#`),
`home_team`, `away_team`, `kickoff`, `is_prematch`, `markets` and `scraped_at`. `markets` holds
the market the page shows on load (1X2 for a football URL ending in `#<id>`) as
`{market, scope, outcomes}`, each outcome `{outcome, votes_pct}`: the label of its odds column
(`1`, `X`, `2`) and its rounded share of the votes. A finished match can keep its votes:
`is_prematch` is `false` once the header shows the live marker or a score. When the page shows
no vote row, `markets` is empty and the command exits 1. Its `kickoff` reads like the match
header, weekday first (`Sunday, 04 Jan 2026, 17:30`), in the browser timezone (`--timezone`).

**Limitations:** `--match-url` reads one market, the one shown on load, and only as
percentages, since the page no longer carries vote counts (gotchas §19). `--user` captures
the first rendered predictions batch (no deep pagination) and does not emit per-prediction
win/loss (use the monthly stats table).

### `oddsharvester team`

Scrape team metadata from OddsPortal team pages: identity, venue, coach and recent form. One record per team.

```bash
# By team id, as it appears in an OddsPortal URL
oddsharvester team --team lId4TMwf --headless

# Several teams at once, by id or by pasted team page URL, into a spreadsheet
oddsharvester team --team lId4TMwf,WGt8En5I --headless -f csv -o teams.csv

# From a file holding one id or URL per line
oddsharvester team --teams-file my_teams.txt --headless -o teams.json
```

Each record carries `team_id`, `name`, `full_name`, `list_name`, `sport`, `country`, `town`,
`venue`, `coach`, `tournament`, `logo_url`, the Last 6 Games block (`form`, `over_2_5_pct`,
`btts_pct`, `avg_goals_scored`, `avg_goals_conceded`), the canonical `team_url` and `scraped_at`.

`list_name` is the short name OddsPortal prints in match lists, which is the one to join on: a
team can appear as "Barcelona FC" on its own page and "Barcelona" in a fixture list. It is read
from the recent-form block, so it survives a page that shows no odds rows at all.

**Limitations:** `country`, `town` and `venue` are simply absent for smaller teams, and
`tournament` only appears on fixture rows, which your IP's selected bookmakers may leave empty.
A wrong team id is reported as a failure rather than written as a blank record: the page it
returns builds its heading from the URL and otherwise looks valid.

Team pages are loaded one after the other, `--request-delay` seconds apart (default `1.0`), so a
run of N teams takes about N seconds more than the pages themselves.

### CLI Options Reference

The **Commands** column names the commands that take each option; `all` stands for all five.

#### Global Options

Given before the command name, e.g. `oddsharvester -v upcoming ...`.

| Option      | Short | Description                        |
| ----------- | ----- | ---------------------------------- |
| `--verbose` | `-v`  | Log at DEBUG level                 |
| `--quiet`   | `-q`  | Log errors only; wins over `-v`    |
| `--version` |       | Print the version and exit         |

#### Core Options

| Option         | Short | Commands | Description                                                                | Default    |
| -------------- | ----- | -------- | -------------------------------------------------------------------------- | ---------- |
| `--sport`      | `-s`  | upcoming, historic, live, community | Sport to scrape (`football`, `tennis`, `basketball`, etc.). On `community` it selects the top-predictions mode, one of three | _required_ on upcoming, historic and live |
| `--date`       | `-d`  | upcoming | Target date in `YYYYMMDD` format. Refused only once that date is over in every timezone (UTC-12 included), so the machine's timezone does not matter | —          |
| `--league`     | `-l`  | upcoming, historic, live | Comma-separated league slugs (e.g. `england-premier-league`), or league paths for leagues outside the built-in list (e.g. `football/bhutan/premier-league`, or the full oddsportal.com URL) | —          |
| `--market`     | `-m`  | upcoming, historic, live | Comma-separated markets (e.g. `1x2,btts`)                                  | —          |
| `--match-link` |       | upcoming, historic, live | Specific match URLs, comma-separated and/or repeated. Skips listing pages; `--date` and `--league` are then ignored (`--league` with a warning), and `historic` writes a given `--season` into the records | —          |
| `--match-links-file` |       | upcoming, historic, live | File with match URLs to scrape, one per line. Combines with `--match-link`; duplicates are dropped | —          |

**`--match-link` usage:** `--sport` is still required. Match links bypass the listing pages entirely, so `upcoming` and `historic` scrape any match, played or not. `historic` takes an optional `--season` (one at most) and writes it into each record's `season` field, which the match page does not give. For large link sets (a `--links-only` output, re-running failures), prefer `--match-links-file`: a pasted command line gets silently truncated by the terminal past a few hundred URLs.

**`upcoming` only:** `--date` is required unless `--league` or `--match-link` is provided. `--date` and `--league` can be combined to filter the league's upcoming matches down to a specific calendar day. When combining both, the reference timezone for resolving the date is `--timezone` if provided, otherwise the host's timezone. `--kickoff-within-hours N` keeps only matches starting within `N` hours from now; the filter runs during link collection, so far-off matches are never visited. It pairs with the default upcoming-only behaviour to bound the window on both sides; the window is counted in real hours from now, whatever the timezone. Combined with `--links-only`, each row also carries `kickoff_utc`, so a scheduler can plan a day of fixtures from one listing request instead of re-fetching the listing on every cycle.

| Option                   | Commands | Description                               | Default    |
| ------------------------ | -------- | ----------------------------------------- | ---------- |
| `--include-started`      | upcoming | Also return matches that have already started or finished (`--no-include-started` to opt out explicitly) | `--no-include-started` |
| `--kickoff-within-hours` | upcoming | Only scrape matches kicking off within this many hours from now (a number above 0) | no limit |

**`historic` only:**

| Option        | Commands | Description                               | Default    |
| ------------- | -------- | ----------------------------------------- | ---------- |
| `--season`    | historic | Comma-separated seasons to scrape (`YYYY`, `YYYY-YYYY`, or `current`). Scraped as the cartesian product with `--league`. Duplicates are ignored. With `--match-link`, optional: one season, written into the records. | _required_ with `--league` |
| `--max-pages` | historic | Max number of result pages to scrape. Applies per league/season combo, not per run. | unlimited  |

`historic` needs `--league` or `--match-link`; without either it exits 2 before the browser starts.

**`live` only:** no `--date` and no `--season`; the command always reads whatever is in
play at the moment it runs. `--league` accepts **at most one** slug. `--odds-history` is
rejected and `--period` accepts only the sport's full-match period, because the in-play view
exposes no history and no period selector. `--links-only` cannot be combined with
`--local-kickoff`, as on `upcoming` and `historic`. A
`--match-link` given in classic form is normalized to its in-play URL automatically, so
either form works. When every match fails to scrape the command exits non-zero, which is
what lets a scheduled sampler tell a blocked run apart from a genuinely empty one.

#### Community and Team Options

| Option         | Commands  | Description                                                                 |
| -------------- | --------- | --------------------------------------------------------------------------- |
| `--user`       | community | User-profile mode: an OddsPortal username                                   |
| `--match-url`  | community | Match-community mode: an OddsPortal match URL                               |
| `--team`       | team      | Team to scrape, as an OddsPortal team id or a team page URL. Comma-separated and/or repeated |
| `--teams-file` | team      | File with teams to scrape, one id or URL per line. Combines with `--team`   |

`community` takes exactly one of `--sport`, `--user` and `--match-url`; `team` needs `--team` or `--teams-file`. Both exit 2 before the browser starts otherwise.

#### Output Options

| Option      | Short | Commands | Description                                                                | Default        |
| ----------- | ----- | -------- | -------------------------------------------------------------------------- | -------------- |
| `--storage` |       | all      | `local` or `remote` (S3, see [Uploading to S3](#uploading-to-s3))            | `local`        |
| `--format`  | `-f`  | all      | `json` or `csv`                                                            | `json`         |
| `--output`  | `-o`  | all      | Output file path                                                           | `scraped_data` |
| `--append`  |       | all      | Append to the output file instead of overwriting it (`--no-append` to opt out explicitly). CSV rows follow the file's own header; a batch with new columns widens it and earlier rows get empty cells | `--no-append`  |
| `--links-only` |       | upcoming, historic, live | Collect match links only, without scraping odds (`--no-links-only` to opt out explicitly) | `--no-links-only` |
| `--local-kickoff` |       | upcoming, historic, live | Add venue-local kickoff time to each record (`--no-local-kickoff` to opt out explicitly). Distinct from `--timezone` | `--no-local-kickoff` |
| `--stream-ndjson` |       | upcoming, historic, live | Emit each match as an NDJSON line on stdout as soon as it is scraped (`--no-stream-ndjson` to opt out explicitly) | `--no-stream-ndjson` |

> **Breaking change:** a run now exits 1 when its output cannot be written. The batch is
> then saved next to the requested output as `<name>.unsaved-<UTC timestamp>.json`, and the
> message gives that path. `--append` onto an existing JSON file that is not a readable list
> (invalid JSON, which used to be overwritten, or JSON that is not a list, which used to fail
> silently) leaves that file as it was and sends the batch to the fallback file. JSON output,
> and CSV output without `--append`, is written to a temporary file first and then moved into
> place, so an interrupted run never leaves a truncated file. When the output's folder does
> not allow a temporary file, the output is written in place as before. `historic` and
> `upcoming` also exit 1 when a league or season fails to list, after writing the data of the
> others.

> **Breaking change:** every output row now carries a `season` column. For odds
> rows it is inserted directly after `match_date`; `--links-only` rows have no
> `match_date` and carry `season` alongside the other link fields instead. It
> holds the scraped season for `historic`, including the `--season` given with
> `historic --match-link`, and is empty for `upcoming` and other `--match-link`
> runs. Appending to a file produced by an earlier version
> yields a file with two different column layouts, so start a new output file
> rather than appending across the upgrade.

> **Breaking change:** `upcoming --links-only` rows now carry a `kickoff_utc`
> column, appended at the end. Appending to a file produced by an earlier
> version yields a file with two different column layouts, so start a new
> output file rather than appending across the upgrade. `live` links-only rows
> are unchanged; `historic` ones gain `match_day` (below).

> **Breaking change:** `historic --links-only` rows now carry a `match_day`
> column, appended at the end. Appending to a CSV file produced by an earlier
> version widens its header: earlier rows get an empty `match_day`. `upcoming`
> and `live` links-only rows are unchanged.

> **Breaking change:** `boto3` moved to the `s3` extra, so `pip install oddsharvester` no longer
> installs it, and there is no default S3 bucket any more. `--storage remote` (or
> `OH_STORAGE=remote`) needs `pip install 'oddsharvester[s3]'` and a bucket in `OH_S3_BUCKET`;
> without either, the command exits 2 before the browser starts and names the missing piece.
> Remote storage now honours `--format` and `--append` the same way local storage does (it used
> to always write JSON and always overwrite), and the object key carries the file's extension
> when `-o` has none, e.g. `-o out` now uploads `out.json`.

#### Browser & Scraping Options

| Option            | Short | Commands | Description                               | Default |
| ----------------- | ----- | -------- | ----------------------------------------- | ------- |
| `--headless`      |       | all      | Run browser in headless mode              | `False` |
| `--concurrency`   | `-c`  | upcoming, historic, live | Concurrent scraping tasks: match pages, and league listings when several leagues are given. On `historic` each parallel listing walks its own result pages, so `-c` also multiplies the listing-page request rate; lower it for large league/season products. | `3`     |
| `--request-delay` |       | upcoming, historic, live, team | Delay (sec) between match pages, between league/season listings (one per combo) and between team pages. The result pages of one listing keep their own 6 to 8 s pause | `1.0`   |
| `--user-agent`    |       | all      | Custom browser user agent                 | the browser's own, `HeadlessChrome` renamed `Chrome` |
| `--locale`        |       | all      | Browser locale (e.g. `fr-BE`), also sent as Accept-Language | `en-US` |
| `--timezone`      |       | all      | Browser timezone (e.g. `Europe/Brussels`) | —       |
| `--base-url`      |       | all      | Scrape a regional OddsPortal mirror instead of `www.oddsportal.com` (e.g. `https://www.centroquote.it`). Page structure is identical; only the domain changes. Regional mirrors may expose a different/larger set of bookmakers. Recommended: pair with `--locale`/`--timezone` matching the region. Env var: `OH_BASE_URL`. | —       |

#### Proxy Options

| Option         | Commands | Description                                                                                                                                                             |
| -------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--proxy-url`  | all      | Proxy URL (`http://...` or `socks5://...`). **Repeatable** — pass it multiple times to rotate per-match scraping round-robin across proxies. Each URL may embed credentials (`scheme://user:pass@host:port`). |
| `--proxy-user` | all      | Proxy username. Applies only when a **single** `--proxy-url` without embedded credentials is given; ignored (with a warning) if multiple proxies are passed.           |
| `--proxy-pass` | all      | Proxy password. Same single-proxy restriction as `--proxy-user`.                                                                                                       |

League listings always load on the first proxy's browser context; only match pages rotate across the configured proxies.

> **Tip:** For best results, match `--locale` and `--timezone` to your proxy's region.

**Multi-proxy example** — spread scraping across three proxies with embedded credentials:

```bash
oddsharvester historic --sport football --league england-premier-league --season 2013-2014 \
  --market 1x2 --concurrency 6 \
  --proxy-url http://user:pass@p1.example.com:8000 \
  --proxy-url http://user:pass@p2.example.com:8000 \
  --proxy-url http://user:pass@p3.example.com:8000
```

Matches are dispatched round-robin across the proxies; a proxy that fails 3 times in a row (navigation/rate-limit errors) is dropped from rotation and the run continues on the survivors.

#### Advanced Options

| Option               | Commands | Description                                            | Default        |
| -------------------- | -------- | ------------------------------------------------------ | -------------- |
| `--target-bookmaker` | upcoming, historic, live | Filter odds for a specific bookmaker                   | —              |
| `--odds-history`     | upcoming, historic, live | Include historical odds movement per match; `live` refuses it | `False`        |
| `--preview-only`     | upcoming, historic, live | Read the best odds of each submarket line instead of every bookmaker's (faster); a market without lines, such as 1X2, falls back to the full bookmaker table. `--full-scrape` asks for the full mode | `--full-scrape` |
| `--bookies-filter`   | upcoming, historic, live | Bookmaker filter: `all`, `classic`, or `crypto`        | `all`          |
| `--period`           | upcoming, historic, live | Match period (sport-specific: full-time, halves, etc.); `live` accepts only the full-match period | sport default  |

> **Deprecated:** `--odds-format` never changed anything: odds are always decimal. It is
> hidden from `--help`, a non-decimal value prints a warning, and it will be removed in a
> future release.

> **Breaking change:** `--odds-history` timestamps now carry the match's year
> (the year before kickoff for a December opening of a January match) instead of
> the year the scraper runs in. They stay naive (no UTC offset) and are in the
> browser timezone: `--timezone` when given, otherwise the host's. Every
> bookmaker entry gets exactly one `odds_history_data` block per outcome, in
> outcome order; a block whose history cannot be read is
> `{"odds_history": [], "opening_odds": null}` instead of being dropped, which
> used to shift the remaining blocks. A market requested for a
> non-default `--period` that cannot be verified on the page is now returned empty
> instead of carrying another period's odds.
> Every period is selected through its URL scope code, on `www.oddsportal.com` and
> on regional mirrors alike, and a non-default period is kept only when the page
> shows that period's tab (a later tab is bold, or the first tab, once clicked,
> writes that period's scope): a period the match does not offer (for example NFL
> `2nd_half` or baseball `full_time` on a match without that tab) comes back empty
> instead of carrying the default period's odds.

<details>
<summary><strong>Preview Mode vs Full Mode</strong></summary>
<br>

| Aspect           | Full Mode                   | Preview Mode                  |
| ---------------- | --------------------------- | ----------------------------- |
| **Speed**        | Slower (interactive)        | Faster (passive)              |
| **Data**         | All submarkets + bookmakers | Visible submarkets + best odds |
| **Bookmakers**   | Individual bookmaker odds   | Best/highest odds only        |
| **Odds History** | Available                   | Not available                 |
| **Structure**    | By bookmaker                | By submarket (best odds)      |

Preview mode (`--preview-only`) is useful for quick exploration, testing data format, or light monitoring with reduced resource usage. It reads the collapsed submarket row — the single best/highest price OddsPortal shows per line, not a per-bookmaker breakdown and not a computed average (see `docs/agentic-gotchas.md` §12).

</details>

### Two-pass workflow: collect links, then scrape

For large runs it can be safer to collect all match links first, then scrape odds per link and re-run only the failures (see issue #75):

```bash
# Pass 1 - collect the season's match links (no odds scraped)
oddsharvester historic -s football -l england-premier-league --season 2022-2023 \
    --links-only -f csv -o links.csv

# Pass 2 - scrape odds from the collected links (--append fills recovered failures)
tail -n +2 links.csv | cut -d, -f1 | sort -u > links.txt
oddsharvester upcoming -s football -m 1x2 -f csv -o odds.csv --append \
    --match-links-file links.txt
```

On `upcoming`, the same pass 1 doubles as a fixture plan: one listing request
returns every match of the day with its kickoff, so a scheduler can decide
offline which matches are close enough to be worth scraping.

```bash
# Plan the day's fixtures: links plus kickoff, no odds scraped
oddsharvester upcoming -s football -d $(date +%Y%m%d) --links-only -f csv -o upcoming_links.csv
```

Output rows contain `match_link`, `sport`, `league`, and `season` (`date` and `kickoff_utc` for `upcoming`, `match_day` for `historic`; `live` emits none of them), in the site's listing order. `match_day` (`2025-05-25`) is the day of the date header the results page groups the match under, as the browser renders it, so in the `--timezone` zone (a results page shows no kickoff time), and is empty for a row with no readable date header above it. `kickoff_utc` holds the match's own kickoff in UTC, in the same shape as `match_date` (`2026-07-31 18:30:00 UTC`), and is empty when the listing exposes no parseable kickoff. Under the default upcoming-only behaviour that means the date header could not be read or the row's first column held no `HH:MM` clock; with `--include-started`, a row whose first column shows a status or a period marker instead of the clock (a live or finished match) also comes back with an empty `kickoff_utc`. Options that only affect odds scraping (`--market`, `--period`, `--odds-history`, `--preview-only`, `--target-bookmaker`, `--bookies-filter`) are ignored when `--links-only` is set. `--links-only` cannot be combined with `--match-link`.

### Bulk scraping: multiple leagues, multiple seasons

`--season` and `--league` both accept comma-separated lists. `historic` scrapes every combination as the cartesian product, league outer and season inner; listings run up to `--concurrency` at once, but output still stays grouped and deterministic per combo. `--max-pages` applies per combo, not per run.

```bash
# Several seasons of one league
oddsharvester historic --sport football --league england-premier-league \
    --season 2020-2021,2021-2022,2022-2023 --links-only --format csv --output links.csv

# Cartesian product: every league by every season
oddsharvester historic --sport football \
    --league england-premier-league,spain-laliga \
    --season 2021-2022,2022-2023 --links-only

# A league that changed season format mid-history: pass both formats and
# let the invalid pairs report zero
oddsharvester historic --sport football --league russia-premier-league \
    --season 2010,2010-2011,2011,2011-2012 --links-only
```

No pre-filtering is attempted to figure out which `(league, season)` pairs are valid before scraping them; a wrong-format pair (e.g. `2010` for a league that only ever used `2010-2011`) is simply scraped and returns zero links. That is normal, not an error: OddsPortal returns HTTP 200 for a dead season URL, so the only way to tell a valid combo from an invalid one is to scrape it and count the results (see `docs/agentic-gotchas.md` §15). When more than one combo runs, an end-of-run table lists each league/season pair with its count, then reports how many combos returned nothing and how many errored. A zero-count combo does not fail the run while another combo returns data; when every combo returns nothing, the run exits 1, as any run that scraped no match does. An errored combo makes the run exit 1 once the other combos' data is written, and is the only kind worth re-running.

### Local kickoff time

`--local-kickoff` adds two fields to each record: `venue_timezone` (the venue's IANA timezone id) and `match_date_venue_local` (the kickoff converted to that timezone, with an explicit offset), e.g. `2022-05-01 16:00:00 BST+0100`. `match_date` stays UTC; the two fields are additive and only appear when the flag is set.

Resolution is best-effort from the record's venue country/town. Single-timezone countries resolve by country; USA, Canada, Mexico, Brazil, Russia, and Australia resolve by host city instead. A venue that can't be resolved gets `null` for both fields.

Not compatible with `--links-only` (no match pages are visited, so there's no venue to resolve). Distinct from `--timezone`, which sets the browser's context timezone (the host's when unset): a league listing groups its dates in that zone, so it decides which matches `-d` keeps there, and the community `kickoff` fields and the `--odds-history` timestamps are given in it.

Appending to an existing CSV file adds the two columns to its header; rows written before carry them empty.

### Streaming results while the run is in progress

By default a run collects every match and writes the whole batch at the end, so a 10-match run
hands you nothing for 10 minutes. `--stream-ndjson` emits each match on stdout as a single JSON
line the moment that match is done, letting a downstream process start work while the rest is
still being scraped:

```bash
oddsharvester upcoming -s football -d $(date +%Y%m%d) -m 1x2 --stream-ndjson --headless \
    | while read -r line; do echo "$line" | jq -r '.home_team + " vs " + .away_team'; done
```

Each line is exactly the record that `--output` would have written, so a consumer parses the same
shape either way. Logs, the run summary and the failed-URL list all go to stderr, leaving stdout
carrying nothing but NDJSON.

Without `--output`, no result file is written at all — the stream is the output. Pass `--output` to
keep a batch file as well; `--format` then governs that file only, the stream stays NDJSON.

Failures are not streamed: they stay visible on stderr and in the exit code. Available on
`upcoming`, `historic` and `live`; not compatible with `--links-only`, which never visits match
pages. A run that spans several leagues or seasons streams every match into one flat sequence with
no marker between combos.

### Uploading to S3

`--storage remote` writes the output file exactly as `--storage local` does, then uploads that file
to an S3 bucket:

```bash
pip install 'oddsharvester[s3]'
export OH_S3_BUCKET=my-odds-bucket
export OH_AWS_REGION=eu-west-1   # optional, default eu-west-3
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2 \
    --storage remote -f csv -o data/epl.csv
```

The object key is the local path as written: `data/epl.csv` above, `scraped_data.json` without
`--output`. The local file stays on disk, and `--format` and `--append` apply to it as they do
locally, so each run uploads the whole file. Credentials come from the usual AWS sources
(environment variables, `~/.aws/credentials`, an instance role). When the upload fails, the command
exits 1 and names both the local file that holds the records and the `s3://` location it could not
reach. With `--stream-ndjson`, remote storage needs `--output`, since the stream alone writes no
file to upload.

### Blocked odds

OddsPortal strikes through a price when that bookmaker has stopped offering the bet. Each per-bookmaker odds record then carries a `blocked_outcomes` field listing which outcomes are struck through, using the same labels as the odds themselves:

```json
{
  "bookmaker_name": "Unibet.fr",
  "1": "1.32",
  "X": "4.55",
  "2": "6.10",
  "blocked_outcomes": ["1", "X", "2"]
}
```

The labels are the market's own, so they differ per market: `1` / `X` / `2` for 1X2, `odds_over` / `odds_under` for Over/Under, and so on.

The field is always collected, with no flag to enable, and is **omitted entirely when nothing is blocked**, so records for available odds are unchanged. Odds values are kept exactly as rendered: a struck-through price is still the last price that bookmaker showed. A bookmaker with no price at all renders `-` and is not flagged, so "no odds" and "blocked" stay distinguishable.

---

## Environment Variables

The options in the table below can also be set through an environment variable, which is handy for Docker or CI/CD; a value given on the command line wins over the variable. The other options have no variable and are set on the command line only.

<details>
<summary><strong>View all environment variables</strong></summary>
<br>

| Variable           | CLI Option        | Description                  |
| ------------------ | ----------------- | ---------------------------- |
| `OH_SPORT`         | `--sport`         | Sport to scrape              |
| `OH_LEAGUES`       | `--league`        | Comma-separated leagues      |
| `OH_MARKETS`       | `--market`        | Comma-separated markets      |
| `OH_STORAGE`       | `--storage`       | Storage type (local/remote)  |
| `OH_FORMAT`        | `--format`        | Output format (json/csv)     |
| `OH_FILE_PATH`     | `--output`        | Output file path             |
| `OH_APPEND`        | `--append`        | Append to the output file instead of overwriting |
| `OH_LINKS_ONLY`    | `--links-only`    | Collect match links only, without scraping odds |
| `OH_INCLUDE_STARTED` | `--include-started` | Also return matches that have already started or finished |
| `OH_TEAMS`         | `--team`          | Teams to scrape, as ids or team page URLs |
| `OH_USER`          | `--user`          | Community user-profile mode: OddsPortal username |
| `OH_MATCH_URL`     | `--match-url`     | Community match mode: OddsPortal match URL |
| `OH_LOCAL_KICKOFF` | `--local-kickoff` | Add venue-local kickoff time to each record |
| `OH_STREAM_NDJSON` | `--stream-ndjson` | Emit each match as an NDJSON line on stdout while scraping |
| `OH_HEADLESS`      | `--headless`      | Run in headless mode         |
| `OH_CONCURRENCY`   | `--concurrency`   | Number of concurrent tasks   |
| `OH_REQUEST_DELAY` | `--request-delay` | Delay between match pages, listings and team pages (sec) |
| `OH_PROXY_URL`     | `--proxy-url`     | Proxy server URL(s) — space-separated for multiple proxies |
| `OH_PROXY_USER`    | `--proxy-user`    | Proxy username               |
| `OH_PROXY_PASS`    | `--proxy-pass`    | Proxy password               |
| `OH_USER_AGENT`    | `--user-agent`    | Custom browser user agent    |
| `OH_LOCALE`        | `--locale`        | Browser locale               |
| `OH_TIMEZONE`      | `--timezone`      | Browser timezone ID          |
| `OH_BASE_URL`      | `--base-url`      | Regional OddsPortal mirror base URL |
| `OH_S3_BUCKET`     | none              | S3 bucket that `--storage remote` uploads to (required for remote storage) |
| `OH_AWS_REGION`    | none              | AWS region of that bucket (default `eu-west-3`) |

</details>

```bash
export OH_SPORT=football
export OH_HEADLESS=true
export OH_PROXY_URL=http://proxy.example.com:8080

oddsharvester upcoming -d $(date +%Y%m%d) -m 1x2
```

---

## Installation

### With pip (from PyPI)

```bash
pip install oddsharvester

# With S3 upload (--storage remote)
pip install 'oddsharvester[s3]'
```

### From source (with uv)

```bash
git clone https://github.com/jordantete/OddsHarvester.git
cd OddsHarvester
pip install uv
uv sync
```

<details>
<summary><strong>Manual setup (venv + pip or poetry)</strong></summary>
<br>

```bash
python3 -m venv .venv
source .venv/bin/activate    # Unix/macOS
# .venv\Scripts\activate     # Windows

pip install . --use-pep517
# or: poetry install
```

</details>

### Browser

Playwright downloads its Chromium separately, once per machine:

```bash
playwright install chromium          # after pip install
uv run playwright install chromium   # from source
```

On a Linux server, add `--with-deps` to install the system libraries the browser needs too
(`playwright install --with-deps chromium`). Runs use Playwright's full Chromium build, headless or
not: an install made with `--only-shell` is not enough.

Verify installation:

```bash
oddsharvester --help
```

---

## Docker

```bash
# Build
docker build -t odds-harvester:local .

# Run (CLI args are appended to the ENTRYPOINT `python3 -m oddsharvester`)
docker run --rm odds-harvester:local upcoming -s football -d $(date +%Y%m%d) -m 1x2 --headless

# Run and keep the JSON output on the host (mount a volume + use -o)
# On macOS+colima, prefer a path under $HOME (e.g. $PWD); /tmp is not shared by default.
docker run --rm -v "$PWD/_docker_out:/out" odds-harvester:local \
  upcoming -s football -d $(date +%Y%m%d) -m 1x2 --headless -o /out/result.json

# Or with environment variables
docker run --rm \
  -e OH_SPORT=football \
  -e OH_HEADLESS=true \
  odds-harvester:local upcoming -d $(date +%Y%m%d) -m 1x2
```

---

## Contributing

Contributions are welcome! Submit an issue or pull request. Please follow the project's coding standards and include clear descriptions for any changes.

## License

[MIT License](./LICENSE.txt)

## Disclaimer

This package is intended for educational purposes only. The author is not affiliated with or endorsed by oddsportal.com. Use responsibly and ensure compliance with their terms of service and applicable laws.
