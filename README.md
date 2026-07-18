<div align="center">

# OddsHarvester

### Scrape sports betting odds from OddsPortal.com with ease

Extract upcoming & historical odds, plus community predictions, tipster profiles and per-match votes, across 10 sports, 100+ leagues, and dozens of betting markets.
<br>Powered by Playwright browser automation. Output to JSON, CSV, or S3.

<br>

[![PyPI version](https://img.shields.io/pypi/v/oddsharvester.svg?style=flat-square)](https://pypi.org/project/oddsharvester/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/github/actions/workflow/status/jordantete/OddsHarvester/run_unit_tests.yml?style=flat-square&label=tests)](https://github.com/jordantete/OddsHarvester/actions)
[![Scraper Health](https://img.shields.io/github/actions/workflow/status/jordantete/OddsHarvester/scraper_health_check.yml?style=flat-square&label=scraper%20health)](https://github.com/jordantete/OddsHarvester/actions/workflows/scraper_health_check.yml)
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

# Scrape upcoming football matches
oddsharvester upcoming -s football -d 20250301 -m 1x2 --headless

# Scrape historical Premier League odds
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2 --headless

# Scrape community data (top predictions here; also --user profiles and --match-url votes)
oddsharvester community -s football --headless
```

---

## Features

|                  | Feature                 | Description                                                                |
| ---------------- | ----------------------- | -------------------------------------------------------------------------- |
| **Upcoming**     | Scrape upcoming matches | Fetch odds and event details for upcoming sports matches by date or league |
| **Historic**     | Scrape historical odds  | Retrieve past odds and match results for any season                        |
| **Community**    | Scrape community data   | Top predictions, tipster profiles (stats + picks), and per-match community votes |
| **Multi-market** | Advanced parsing        | Structured data: dates, teams, scores, venues, and per-bookmaker odds      |
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

> **Umbrella tokens (football):** `over_under` and `asian_handicap` are umbrella market tokens — pass either as `--market` and it expands at scrape time to every line OddsPortal actually renders for that match (e.g. `over_under_1_5_market`, `over_under_2_5_market`, …), instead of listing each line by hand.

100+ leagues supported across all sports: Premier League, La Liga, Serie A, NBA, NFL, MLB, NHL, ATP/WTA Grand Slams, and [many more](src/oddsharvester/utils/sport_league_constants.py).

---

## CLI Usage

OddsHarvester has three commands: **`upcoming`**, **`historic`**, and **`community`**. They share most options, with a few command-specific ones.

### `oddsharvester upcoming`

Scrape odds for upcoming matches — by date, by league, or by specific match URL.

```bash
# By date
oddsharvester upcoming -s football -d 20250301 -m 1x2 --headless

# By league (scrapes all upcoming matches for that league)
oddsharvester upcoming -s football -l england-premier-league -m 1x2,btts --headless

# Multiple leagues
oddsharvester upcoming -s football -l england-premier-league,spain-laliga -m 1x2 --headless

# Specific match URLs (repeat the flag; works for past matches too)
oddsharvester upcoming -s football --match-link "https://www.oddsportal.com/football/..." -m 1x2

# Preview mode (faster — best/highest odds only, no individual bookmakers)
oddsharvester upcoming -s football -d 20250301 -m over_under --preview-only --headless

# Only matches kicking off within the next 6 hours (fewer requests)
oddsharvester upcoming -s football -l england-premier-league -m 1x2 --kickoff-within-hours 6 --headless
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

### `oddsharvester community`

Scrape OddsPortal Community data. `community` has three mutually-exclusive modes; exactly one is required:

- **Top predictions** (`--sport`): the most-voted community picks for the next 7 days.
- **User profile** (`--user <username>`): a tipster's stats, monthly performance and recent predictions.
- **Match community votes** (`--match-url <url>`): per-market community vote volume for a single match.

#### Top predictions (`--sport`)

```bash
# Top predictions for a sport
oddsharvester community -s football --headless

# Write to a named JSON file
oddsharvester community -s football -f json -o top_predictions.json --headless
```

Each record contains the match (`home_team`, `away_team`, `match_url`, `kickoff`, plus the raw `kickoff_text` label kept as fallback when the date token fails to parse), the league (`sport`, `country`, `league`), the voted `market`, best odds per outcome (`odds`), the community vote split (`community_votes_pct`), and `scraped_at`.

- OddsPortal surfaces ~10 picks per sport (no pagination) with rounded percentages.
- Pre-match only: OddsPortal drops community data from finished-match pages, so build longitudinal datasets by scraping while matches are still upcoming.

#### User profile (`--user <username>`)

```bash
oddsharvester community --user BLAPRO --headless
```

Emits one record: header (`username`, `roi_pct`, `member_since`, `country`, `privacy`), the
monthly `statistics` table (`month`, `total_predictions`, `won`, `lost`, `plus_minus`,
`roi_pct`, incl. a `Total` row), and the rendered `predictions` batch. Each prediction has
`market`, `home_team`/`away_team`, `score` (when finished), and a positional `outcomes` list
of `{odds, community_pct, picked}` plus `pick_odds`. Most profiles are **private**: a private
profile returns the header only (`privacy: "private"`, empty stats/predictions) and exits 0.

#### Match community votes (`--match-url <url>`)

```bash
oddsharvester community --match-url "https://www.oddsportal.com/football/h2h/.../" --headless
```

Emits one record with per-market community vote volume: `markets[]` of `{market, scope,
handicap, betting_type_id, scope_id, total_votes, outcome_counts}`, most-voted first, plus
`top_community_pick`. Pre-match only (OddsPortal drops community data from finished matches).

**Limitations:** `--match-url` outcome vote **counts are unlabeled**: OddsPortal obfuscates the
per-outcome ids, so only per-market volume, the count distribution, and the single aggregate
pick are recoverable. `--user` captures the first rendered predictions batch (no deep
pagination) and does not emit per-prediction win/loss (use the monthly stats table).

### CLI Options Reference

#### Core Options

| Option         | Short | Description                                                                | Default    |
| -------------- | ----- | -------------------------------------------------------------------------- | ---------- |
| `--sport`      | `-s`  | Sport to scrape (`football`, `tennis`, `basketball`, etc.)                 | _required_ |
| `--date`       | `-d`  | Target date in `YYYYMMDD` format                                           | —          |
| `--league`     | `-l`  | Comma-separated league slugs (e.g. `england-premier-league`)               | —          |
| `--market`     | `-m`  | Comma-separated markets (e.g. `1x2,btts`)                                  | —          |
| `--match-link` |       | Specific match URL (repeatable). Skips listing pages; `--date`/`--league`/`--season` are then ignored | —          |

**`--match-link` usage:** `--sport` is still required. Prefer `upcoming` over `historic` for arbitrary match URLs: match links bypass the listing pages entirely, so `upcoming` also works for matches already played, while `historic` would additionally demand a `--season` it never uses.

**`upcoming` only:** `--date` is required unless `--league` or `--match-link` is provided. `--date` and `--league` can be combined to filter the league's upcoming matches down to a specific calendar day. When combining both, the reference timezone for resolving the date is `--timezone` if provided, otherwise UTC. `--kickoff-within-hours N` keeps only matches starting within `N` hours from now; the filter runs during link collection, so far-off matches are never visited. It pairs with the default upcoming-only behaviour to bound the window on both sides, and uses `--timezone` (else UTC) as the reference clock.

**`historic` only:**

| Option        | Description                               | Default    |
| ------------- | ----------------------------------------- | ---------- |
| `--season`    | Season: `YYYY`, `YYYY-YYYY`, or `current` | _required_ |
| `--max-pages` | Max number of result pages to scrape      | unlimited  |

#### Output Options

| Option      | Short | Description                                                                | Default        |
| ----------- | ----- | -------------------------------------------------------------------------- | -------------- |
| `--storage` |       | `local` or `remote` (S3)                                                   | `local`        |
| `--format`  | `-f`  | `json` or `csv`                                                            | `json`         |
| `--output`  | `-o`  | Output file path                                                           | `scraped_data` |
| `--append`  |       | Append to the output file instead of overwriting it (`--no-append` to opt out explicitly) | `--no-append`  |
| `--links-only` |       | Collect match links only, without scraping odds (`--no-links-only` to opt out explicitly) | `--no-links-only` |

#### Browser & Scraping Options

| Option            | Short | Description                               | Default |
| ----------------- | ----- | ----------------------------------------- | ------- |
| `--headless`      |       | Run browser in headless mode              | `False` |
| `--concurrency`   | `-c`  | Concurrent scraping tasks                 | `3`     |
| `--request-delay` |       | Delay (sec) between match requests        | `1.0`   |
| `--user-agent`    |       | Custom browser user agent                 | —       |
| `--locale`        |       | Browser locale (e.g. `fr-BE`)             | —       |
| `--timezone`      |       | Browser timezone (e.g. `Europe/Brussels`) | —       |
| `--base-url`      |       | Scrape a regional OddsPortal mirror instead of `www.oddsportal.com` (e.g. `https://www.centroquote.it`). Page structure is identical; only the domain changes. Regional mirrors may expose a different/larger set of bookmakers. Recommended: pair with `--locale`/`--timezone` matching the region. Env var: `OH_BASE_URL`. | —       |

#### Proxy Options

| Option         | Description                                                                                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--proxy-url`  | Proxy URL (`http://...` or `socks5://...`). **Repeatable** — pass it multiple times to rotate per-match scraping round-robin across proxies. Each URL may embed credentials (`scheme://user:pass@host:port`). |
| `--proxy-user` | Proxy username. Applies only when a **single** `--proxy-url` without embedded credentials is given; ignored (with a warning) if multiple proxies are passed.           |
| `--proxy-pass` | Proxy password. Same single-proxy restriction as `--proxy-user`.                                                                                                       |

> **Tip:** For best results, match `--locale` and `--timezone` to your proxy's region.

**Multi-proxy example** — spread scraping across three proxies with embedded credentials:

```bash
oddsharvester historic --sport football --leagues england-premier-league --season 2013-2014 \
  --markets 1x2 --concurrency 6 \
  --proxy-url http://user:pass@p1.example.com:8000 \
  --proxy-url http://user:pass@p2.example.com:8000 \
  --proxy-url http://user:pass@p3.example.com:8000
```

Matches are dispatched round-robin across the proxies; a proxy that fails 3 times in a row (navigation/rate-limit errors) is dropped from rotation and the run continues on the survivors.

#### Advanced Options

| Option               | Description                                            | Default        |
| -------------------- | ------------------------------------------------------ | -------------- |
| `--target-bookmaker` | Filter odds for a specific bookmaker                   | —              |
| `--odds-history`     | Include historical odds movement per match             | `False`        |
| `--odds-format`      | Odds display format                                    | `Decimal Odds` |
| `--preview-only`     | Fast mode — best/highest odds, no bookmaker details    | `False`        |
| `--bookies-filter`   | Bookmaker filter: `all`, `classic`, or `crypto`        | `all`          |
| `--period`           | Match period (sport-specific: full-time, halves, etc.) | sport default  |

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

# Pass 2 - scrape odds per link (repeat --match-link; --append fills recovered failures)
oddsharvester historic -s football --season 2022-2023 -m 1x2 -f csv -o odds.csv --append \
    --match-link "https://www.oddsportal.com/football/england/premier-league-2022-2023/..."
```

Output rows contain `match_link`, `sport`, `league`, and `season` (`date` for `upcoming`), in the site's listing order. Options that only affect odds scraping (`--market`, `--period`, `--odds-history`, `--preview-only`, `--target-bookmaker`, `--bookies-filter`) are ignored when `--links-only` is set. `--links-only` cannot be combined with `--match-link`.

---

## Environment Variables

All CLI options can be set via environment variables — useful for Docker or CI/CD.

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
| `OH_HEADLESS`      | `--headless`      | Run in headless mode         |
| `OH_CONCURRENCY`   | `--concurrency`   | Number of concurrent tasks   |
| `OH_REQUEST_DELAY` | `--request-delay` | Delay between requests (sec) |
| `OH_PROXY_URL`     | `--proxy-url`     | Proxy server URL(s) — space-separated for multiple proxies |
| `OH_PROXY_USER`    | `--proxy-user`    | Proxy username               |
| `OH_PROXY_PASS`    | `--proxy-pass`    | Proxy password               |
| `OH_USER_AGENT`    | `--user-agent`    | Custom browser user agent    |
| `OH_LOCALE`        | `--locale`        | Browser locale               |
| `OH_TIMEZONE`      | `--timezone`      | Browser timezone ID          |
| `OH_BASE_URL`      | `--base-url`      | Regional OddsPortal mirror base URL |

</details>

```bash
export OH_SPORT=football
export OH_HEADLESS=true
export OH_PROXY_URL=http://proxy.example.com:8080

oddsharvester upcoming -d 20250301 -m 1x2
```

---

## Installation

### With pip (from PyPI)

```bash
pip install oddsharvester
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
docker run --rm odds-harvester:local upcoming -s football -d 20250301 -m 1x2 --headless

# Run and keep the JSON output on the host (mount a volume + use -o)
# On macOS+colima, prefer a path under $HOME (e.g. $PWD); /tmp is not shared by default.
docker run --rm -v "$PWD/_docker_out:/out" odds-harvester:local \
  upcoming -s football -d 20250301 -m 1x2 --headless -o /out/result.json

# Or with environment variables
docker run --rm \
  -e OH_SPORT=football \
  -e OH_HEADLESS=true \
  odds-harvester:local upcoming -d 20250301 -m 1x2
```

---

## Contributing

Contributions are welcome! Submit an issue or pull request. Please follow the project's coding standards and include clear descriptions for any changes.

## License

[MIT License](./LICENSE.txt)

## Disclaimer

This package is intended for educational purposes only. The author is not affiliated with or endorsed by oddsportal.com. Use responsibly and ensure compliance with their terms of service and applicable laws.
