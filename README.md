# **OddsHarvester**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://github.com/jordantete/OddsHarvester/actions/workflows/run_unit_tests.yml/badge.svg)](https://github.com/jordantete/OddsHarvester/actions)
[![Scraper Health Check](https://github.com/jordantete/OddsHarvester/actions/workflows/scraper_health_check.yml/badge.svg)](https://github.com/jordantete/OddsHarvester/actions/workflows/scraper_health_check.yml)
[![codecov](https://codecov.io/github/jordantete/OddsHarvester/graph/badge.svg?token=DOZRQAXAK7)](https://codecov.io/github/jordantete/OddsHarvester)

OddsHarvester is an application designed to scrape and process sports betting odds and match data from **oddsportal.com** website.

## **📖 Table of Contents**

1. [✨ Features](#-features)
2. [🛠️ Local Installation](#-local-installation)
3. [⚡ Usage](#-usage)
   - [🔧 CLI Commands](#-cli-commands)
   - [🐳 Running Inside a Docker Container](#-running-inside-a-docker-container)
4. [🤝 Contributing](#-contributing)
5. [☕ Donations](#-donations)
6. [📜 License](#-license)
7. [💬 Feedback](#-feedback)
8. [❗ Disclaimer](#-disclaimer)

## **✨ Features**

- **📅 Scrape Upcoming Matches**: Fetch odds and event details for upcoming sports matches.
- **📊 Scrape Historical Odds**: Retrieve historical odds and match results for analytical purposes.
- **🔍 Advanced Parsing**: Extract structured data, including match dates, team names, scores, and venue details.
- **💾 Flexible Storage**: Store scraped data in JSON or CSV locally, or upload it directly to a remote S3 bucket.
- **🐳 Docker Compatibility**: Designed to work seamlessly inside Docker containers with minimal setup.
- **🕵️ Proxy Support**: Route web requests through SOCKS/HTTP proxies for enhanced anonymity, geolocation bypass, and anti-blocking measures.

### 📚 Current Support

OddsHarvester supports a growing number of sports and their associated betting markets. All configurations are managed via dedicated enum and mapping files in the codebase.

#### ✅ Supported Sports & Markets

| 🏅 Sport             | 🛒 Supported Markets                                                                               |
| -------------------- | -------------------------------------------------------------------------------------------------- |
| ⚽ Football          | `1x2`, `btts`, `double_chance`, `draw_no_bet`, `over/under`, `european_handicap`, `asian_handicap` |
| 🎾 Tennis            | `match_winner`, `total_sets_over/under`, `total_games_over/under`, `asian_handicap`, `exact_score` |
| 🏀 Basketball        | `1x2`, `moneyline`, `asian_handicap`, `over/under`                                                 |
| 🏉 Rugby League      | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `over/under`, `handicap`                       |
| 🏉 Rugby Union       | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `over/under`, `handicap`                       |
| 🏒 Ice Hockey        | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `btts`, `over/under`                           |
| ⚾ Baseball          | `moneyline`, `over/under`                                                                          |
| 🏈 American Football | `1x2`, `moneyline`, `over/under`, `asian_handicap`                                                 |

> ⚙️ **Note**: Each sport and its markets are declared in enums inside [`sport_market_constants.py`](src/oddsharvester/utils/sport_market_constants.py).

#### 🗺️ Leagues & Competitions

Leagues and tournaments are mapped per sport in:
[`sport_league_constants.py`](src/oddsharvester/utils/sport_league_constants.py)

You'll find support for:

- 🏆 **Top Football leagues** (Premier League, La Liga, Serie A, etc.)
- 🎾 **Major Tennis tournaments** (ATP, WTA, Grand Slams, etc.)
- 🏀 **Global Basketball leagues** (NBA, EuroLeague, ACB, etc.)
- 🏉 **Major Rugby League competitions** (NRL, Super League, etc.)
- 🏉 **Major Rugby Union competitions** (Six Nations, Rugby Championship, Top 14, etc.)
- 🏒 **Major Ice Hockey leagues** (NHL, KHL, SHL, Liiga, etc.)
- ⚾ **Major Baseball leagues** (MLB, NPB, KBO, etc.)
- 🏈 **American Football leagues** (NFL, NCAA, etc.)

## **🛠️ Local Installation**

1. **Clone the repository**:
   Navigate to your desired folder and clone the repository. Then, move into the project directory:

   ```bash
   git clone https://github.com/jordantete/OddsHarvester.git
   cd OddsHarvester
   ```

2. **Quick Setup with uv**:

   Use [uv](https://github.com/astral-sh/uv), a lightweight package manager, to simplify the setup process. First, install `uv` with `pip`, then run the setup:

   ```bash
   pip install uv
   uv sync
   ```

3. **Manual Setup (Optional)**:

   If you prefer to set up manually, follow these steps:

   - **Create a virtual environment**: Use Python's `venv` module to create an isolated environment (or `virtualenv`) for the project. Activate it depending on your operating system:

     - `python3 -m venv .venv`

     - On Unix/MacOS:
       `source .venv/bin/activate`

     - On Windows:
       `.venv\Scripts\activate`

   - **Install dependencies with pip**: Use pip with the `--use-pep517` flag to install directly from the `pyproject.toml` file:
     `pip install . --use-pep517`.

   - **Or install dependencies with poetry**: If you prefer poetry for dependency management:
     `poetry install`

4. **Verify Installation**:

   Ensure all dependencies are installed and Playwright is set up by running the following command:

   ```bash
   oh --help
   ```

By following these steps, you should have **OddsHarvester** set up and ready to use.

## **⚡ Usage**

### **🔧 CLI Commands**

OddsHarvester provides a Command-Line Interface (CLI) via the `oh` command. Use it to retrieve upcoming match odds, analyze historical data, or store results for further processing.

#### **Global Options**

| 🏷️ Option        | 📝 Description         |
| ---------------- | ---------------------- |
| `-v`, `--verbose` | Enable debug output    |
| `-q`, `--quiet`   | Suppress non-error output |
| `-V`, `--version` | Show version and exit  |

#### **1. Scrape Upcoming Matches** (`oh upcoming`)

Retrieve odds and event details for upcoming sports matches.

```bash
oh upcoming [OPTIONS]
```

**Command-Specific Options:**

| 🏷️ Option | 📝 Description | 🔧 Default |
| --------- | -------------- | ---------- |
| `-d`, `--date DATE` | Date for matches (`YYYY-MM-DD` format) | None |

**Required:** Must provide `--sport` (unless using `--match-link`), and at least one of `--date`, `--league`, or `--match-link`.

#### **2. Scrape Historical Odds** (`oh historic`)

Retrieve historical odds and results for analytical purposes.

```bash
oh historic [OPTIONS]
```

**Command-Specific Options:**

| 🏷️ Option | 📝 Description | 🔧 Default |
| --------- | -------------- | ---------- |
| `--season SEASON` | Season to scrape (`YYYY`, `YYYY-YYYY`, or `current`) | **Required** |
| `--max-pages N` | Maximum number of result pages to scrape | None |

**Required:** `--season` and `--sport` (unless using `--match-link`).

#### **Shared Options**

Both commands share the following options:

| 🏷️ Option | 📝 Description | 🔧 Default | 🌍 Env Var |
| --------- | -------------- | ---------- | ---------- |
| `-s`, `--sport SPORT` | Sport to scrape (`football`, `tennis`, `basketball`, etc.) | None | `OH_SPORT` |
| `-l`, `--league LEAGUE` | League to scrape (repeatable) | None | `OH_LEAGUES` |
| `-m`, `--market MARKET` | Betting market (repeatable, e.g., `1x2`, `btts`) | None | `OH_MARKETS` |
| `--match-link URL` | Specific OddsPortal match URL (repeatable) | None | — |
| `--storage TYPE` | Storage type: `local` or `remote` | `local` | `OH_STORAGE` |
| `-f`, `--format FMT` | Output format: `json` or `csv` | `json` | `OH_FORMAT` |
| `-o`, `--file-path PATH` | Output file path | None | `OH_FILE_PATH` |
| `--headless/--no-headless` | Run browser in headless mode | `--no-headless` | `OH_HEADLESS` |
| `--debug-logs` | Save debug logs to file | `False` | `OH_DEBUG_LOGS` |
| `-c`, `--concurrency N` | Number of concurrent scraping tasks | `3` | `OH_CONCURRENCY` |

**Proxy Options:**

| 🏷️ Option | 📝 Description | 🌍 Env Var |
| --------- | -------------- | ---------- |
| `--proxy-url URL` | Proxy server URL (e.g., `http://proxy.com:8080`) | `OH_PROXY_URL` |
| `--proxy-user USER` | Proxy username | `OH_PROXY_USER` |
| `--proxy-pass PASS` | Proxy password | `OH_PROXY_PASS` |

**Browser Options:**

| 🏷️ Option | 📝 Description | 🌍 Env Var |
| --------- | -------------- | ---------- |
| `--user-agent STRING` | Custom browser user agent | `OH_USER_AGENT` |
| `--locale LOCALE` | Browser locale (e.g., `fr-BE`, `en-US`) | `OH_LOCALE` |
| `--timezone ZONE` | Browser timezone ID (e.g., `Europe/Brussels`) | `OH_TIMEZONE` |

**Advanced Options:**

| 🏷️ Option | 📝 Description | 🔧 Default | 🌍 Env Var |
| --------- | -------------- | ---------- | ---------- |
| `-b`, `--bookmaker NAME` | Filter to specific bookmaker(s) (repeatable) | None | — |
| `--with-odds-history` | Include historical odds movement data | `False` | `OH_ODDS_HISTORY` |
| `--odds-format FMT` | Odds format: `decimal`, `fractional`, `american`, `hong-kong` | `decimal` | `OH_ODDS_FORMAT` |
| `--preview-only` | Only scrape visible submarkets (faster, limited data) | `False` | — |
| `--bookmakers FILTER` | Bookmaker filter: `all`, `classic`, `crypto` | `all` | `OH_BOOKMAKERS` |
| `--period PERIOD` | Match period (see table below) | Sport default | `OH_PERIOD` |

**Period Options by Sport:**

| 🏅 Sport | 🕐 Valid Periods |
| -------- | --------------- |
| ⚽ Football | `ft`, `1h`, `2h` |
| 🎾 Tennis | `ft`, `1s`, `2s` |
| 🏀 Basketball | `ft-ot`, `1h`, `2h`, `1q`, `2q`, `3q`, `4q` |
| 🏉 Rugby League/Union | `ft`, `1h` |
| 🏈 American Football | `ft-ot`, `1h`, `2h`, `1q`, `2q`, `3q`, `4q` |
| 🏒 Ice Hockey | `ft`, `1p`, `2p`, `3p` |
| ⚾ Baseball | `ft-ot`, `ft`, `1h` |

#### **📌 Important Notes:**

- **Repeatable options** (`--league`, `--market`, `--match-link`, `--bookmaker`) can be specified multiple times instead of comma-separated values.
- If `--match-link` is provided, it overrides `--sport`, `--date`, and `--league`.
- For best results, ensure the proxy's region matches your `--locale` and `--timezone` settings.
- All options support environment variables (prefix: `OH_`), useful for CI/CD pipelines.

#### **Example Usage:**

**Upcoming Matches:**

```bash
# Scrape football matches for a specific date
oh upcoming -s football -m 1x2 -d 2025-01-01 --headless

# Scrape multiple leagues with multiple markets
oh upcoming -s football -l england-premier-league -l spain-laliga -m 1x2 -m btts --headless

# Scrape baseball with proxy
oh upcoming -s baseball -d 2025-02-27 -m moneyline \
  --proxy-url http://proxy.com:8080 --proxy-user user --proxy-pass pass --headless

# Scrape in preview mode (faster, average odds only)
oh upcoming -s football -d 2025-01-01 -m over_under --preview-only --headless

# Scrape specific match URLs
oh upcoming --match-link "https://www.oddsportal.com/football/..." \
  --match-link "https://www.oddsportal.com/football/..." -m 1x2
```

**Historical Odds:**

```bash
# Scrape Premier League 2022-2023 season
oh historic -s football -l england-premier-league --season 2022-2023 -m 1x2 --headless

# Scrape multiple leagues
oh historic -s football -l england-premier-league -l spain-laliga -l italy-serie-a \
  --season 2022-2023 -m 1x2 --headless

# Scrape current season
oh historic -s football -l england-premier-league --season current -m 1x2 --headless

# Limit pages scraped
oh historic -s football -l england-premier-league --season 2022-2023 -m 1x2 \
  --max-pages 3 --headless

# Preview mode for faster scraping
oh historic -s football -l england-premier-league --season 2022-2023 \
  -m over_under --preview-only --headless
```

#### **📌 Preview Mode**

The `--preview-only` flag enables a faster scraping mode that extracts only average odds from visible submarkets without loading individual bookmaker details. This mode is useful for:

- **Quick exploration** of available submarkets and their average odds
- **Testing** data structure and format
- **Light monitoring** with reduced resource usage

**Preview Mode vs Full Mode:**

| Aspect           | Full Mode                   | Preview Mode                  |
| ---------------- | --------------------------- | ----------------------------- |
| **Speed**        | Slower (interactive)        | Faster (passive)              |
| **Data**         | All submarkets + bookmakers | Visible submarkets + avg odds |
| **Bookmakers**   | Individual bookmaker odds   | Average odds only             |
| **Odds History** | Available                   | Not available                 |
| **Structure**    | By bookmaker                | By submarket (avg odds)       |

#### **📌 Getting Help:**

```bash
# Show main help
oh --help

# Show command-specific help
oh upcoming --help
oh historic --help
```

### **🐳 Running Inside a Docker Container**

OddsHarvester is compatible with Docker, allowing you to run the application seamlessly in a containerized environment.

**Steps to Run with Docker:**

1. **Ensure Docker is Installed**
   Make sure Docker is installed and running on your system. Visit [Docker's official website](https://www.docker.com/) for installation instructions specific to your operating system.

2. **Build the Docker Image**
   Navigate to the project's root directory, where the `Dockerfile` is located. Build the Docker image using the appropriate Docker build command.
   Assign a name to the image, such as `odds-harvester`: `docker build -t odds-harvester:local --target local-dev .`

3. **Run the Container**
   Start a Docker container based on the built image. Map the necessary ports if required and specify any volumes to persist data. Pass any CLI arguments as part of the Docker run command:
   `docker run --rm odds-harvester:local oh upcoming -s football -d 2025-09-03 -m 1x2 --storage local -o output.json --headless`

4. **Interactive Mode for Debugging**
   If you need to debug or run commands interactively: `docker run --rm -it odds-harvester:latest /bin/bash`

**Tips**:

- **Volume Mapping**: Use volume mapping to store logs or output data on the host machine.
- **Container Reusability**: Assign a unique container name to avoid conflicts when running multiple instances.

## **🤝 Contributing**

Contributions are welcome! If you have ideas, improvements, or bug fixes, feel free to submit an issue or a pull request. Please ensure that your contributions follow the project's coding standards and include clear descriptions for any changes.

## **☕ Donations**

If you find this project useful and would like to support its development, consider buying me a coffee! Your support helps keep this project maintained and improved.

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/pownedj)

## **📜 License**

This project is licensed under the MIT License - see the [LICENSE](./LICENSE.txt) file for more details.

## **💬 Feedback**

Have any questions or feedback? Feel free to reach out via the issues tab on GitHub. We'd love to hear from you!

## **❗ Disclaimer**

This package is intended for educational purposes only and not for any commercial use in any way. The author is not affiliated with or endorsed by the oddsportal.com website. Use this application responsibly and ensure compliance with the terms of service of oddsportal.com and any applicable laws in your jurisdiction.
