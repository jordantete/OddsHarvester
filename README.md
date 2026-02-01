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
   - [🔧 CLI Commands](#cli-commands)
   - [🌐 Environment Variables](#-environment-variables)
   - [🐳 Running Inside a Docker Container](#-running-inside-a-docker-container)
   - [☁️ Cloud Deployment](#-cloud-deployment)
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

> ⚙️ **Note**: Each sport and its markets are declared in enums inside `sport_market_constants.py`.

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
   oddsharvester --help
   ```

   Or using the module directly:

   ```bash
   python -m oddsharvester --help
   ```

By following these steps, you should have **OddsHarvester** set up and ready to use.

## **⚡ Usage**

### **🔧 CLI Commands**

OddsHarvester provides a Command-Line Interface (CLI) to scrape sports betting data from oddsportal.com. Use it to retrieve upcoming match odds, analyze historical data, or store results for further processing.

#### **Quick Reference**

```bash
# Scrape upcoming matches
oddsharvester upcoming -s football -d 20250301 -m 1x2

# Scrape historical data
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2

# Show help
oddsharvester --help
oddsharvester upcoming --help
oddsharvester historic --help
```

#### **1. Scrape Upcoming Matches**

Retrieve odds and event details for upcoming sports matches.

```bash
oddsharvester upcoming [OPTIONS]
```

**Options**:

| Option                    | Short | Description                                                      | Required                              | Default        |
| ------------------------- | ----- | ---------------------------------------------------------------- | ------------------------------------- | -------------- |
| `--sport`                 | `-s`  | Sport to scrape (e.g., `football`, `tennis`, `basketball`)       | Yes                                   | None           |
| `--date`                  | `-d`  | Date for matches in `YYYYMMDD` format                            | Yes (unless `--league` or `--match-link`) | None       |
| `--league`                | `-l`  | Comma-separated leagues (e.g., `england-premier-league`)         | No                                    | None           |
| `--market`                | `-m`  | Comma-separated betting markets (e.g., `1x2,btts`)               | No                                    | None           |
| `--storage`               |       | Storage type: `local` or `remote`                                | No                                    | `local`        |
| `--format`                | `-f`  | Output format: `json` or `csv`                                   | No                                    | `json`         |
| `--output`                | `-o`  | Output file path                                                 | No                                    | `scraped_data` |
| `--headless`              |       | Run browser in headless mode                                     | No                                    | `False`        |
| `--concurrency`           | `-c`  | Number of concurrent scraping tasks                              | No                                    | `3`            |
| `--proxy-url`             |       | Proxy URL (e.g., `http://proxy:8080` or `socks5://proxy:1080`)   | No                                    | None           |
| `--proxy-user`            |       | Proxy username                                                   | No                                    | None           |
| `--proxy-pass`            |       | Proxy password                                                   | No                                    | None           |
| `--user-agent`            |       | Custom browser user agent                                        | No                                    | None           |
| `--locale`                |       | Browser locale (e.g., `fr-BE`)                                   | No                                    | None           |
| `--timezone`              |       | Browser timezone ID (e.g., `Europe/Brussels`)                    | No                                    | None           |
| `--match-link`            |       | Specific match URL(s) to scrape (can be repeated)                | No                                    | None           |
| `--target-bookmaker`      |       | Filter for a specific bookmaker                                  | No                                    | None           |
| `--odds-history`          |       | Scrape historical odds movement                                  | No                                    | `False`        |
| `--odds-format`           |       | Odds display format                                              | No                                    | `Decimal Odds` |
| `--preview-only`          |       | Only scrape visible submarkets (faster, limited data)            | No                                    | `False`        |
| `--bookies-filter`        |       | Bookmaker filter: `all`, `classic`, or `crypto`                  | No                                    | `all`          |
| `--period`                |       | Match period to scrape (sport-specific)                          | No                                    | Sport default  |

**Important Notes:**

- If both `--league` and `--date` are provided, the scraper **will only consider the leagues**, meaning all upcoming matches for those leagues will be scraped.
- If `--match-link` is provided, it overrides `--sport`, `--date`, and `--league`.
- All match links must belong to the same sport when using `--match-link`.
- For best results, ensure the proxy's region matches the `--locale` and `--timezone` settings.

**Example Usage:**

```bash
# Retrieve upcoming football matches for a specific date
oddsharvester upcoming -s football -m 1x2 -d 20250301 --headless

# Scrape English Premier League matches
oddsharvester upcoming -s football -l england-premier-league -m 1x2,btts --headless

# Scrape multiple leagues at once
oddsharvester upcoming -s football -l england-premier-league,spain-laliga -m 1x2 --headless

# Scrape with a proxy
oddsharvester upcoming -s football -d 20250301 -m 1x2 --proxy-url http://proxy:8080 --proxy-user myuser --proxy-pass mypass --headless

# Scrape in preview mode (faster, average odds only)
oddsharvester upcoming -s football -d 20250301 -m over_under --preview-only --headless

# Scrape specific matches using match links
oddsharvester upcoming -s football --match-link "https://www.oddsportal.com/football/..." --match-link "https://www.oddsportal.com/football/..." -m 1x2
```

#### **2. Scrape Historical Odds**

Retrieve historical odds and results for analytical purposes.

```bash
oddsharvester historic [OPTIONS]
```

**Options**:

| Option                    | Short | Description                                                      | Required | Default        |
| ------------------------- | ----- | ---------------------------------------------------------------- | -------- | -------------- |
| `--sport`                 | `-s`  | Sport to scrape (e.g., `football`, `tennis`, `basketball`)       | Yes      | None           |
| `--season`                |       | Season: `YYYY`, `YYYY-YYYY`, or `current`                        | Yes      | None           |
| `--league`                | `-l`  | Comma-separated leagues (e.g., `england-premier-league`)         | No       | None           |
| `--market`                | `-m`  | Comma-separated betting markets (e.g., `1x2,btts`)               | No       | None           |
| `--max-pages`             |       | Maximum number of pages to scrape                                | No       | None           |
| `--storage`               |       | Storage type: `local` or `remote`                                | No       | `local`        |
| `--format`                | `-f`  | Output format: `json` or `csv`                                   | No       | `json`         |
| `--output`                | `-o`  | Output file path                                                 | No       | `scraped_data` |
| `--headless`              |       | Run browser in headless mode                                     | No       | `False`        |
| `--concurrency`           | `-c`  | Number of concurrent scraping tasks                              | No       | `3`            |
| `--proxy-url`             |       | Proxy URL (e.g., `http://proxy:8080` or `socks5://proxy:1080`)   | No       | None           |
| `--proxy-user`            |       | Proxy username                                                   | No       | None           |
| `--proxy-pass`            |       | Proxy password                                                   | No       | None           |
| `--user-agent`            |       | Custom browser user agent                                        | No       | None           |
| `--locale`                |       | Browser locale (e.g., `fr-BE`)                                   | No       | None           |
| `--timezone`              |       | Browser timezone ID (e.g., `Europe/Brussels`)                    | No       | None           |
| `--match-link`            |       | Specific match URL(s) to scrape (can be repeated)                | No       | None           |
| `--target-bookmaker`      |       | Filter for a specific bookmaker                                  | No       | None           |
| `--odds-history`          |       | Scrape historical odds movement                                  | No       | `False`        |
| `--odds-format`           |       | Odds display format                                              | No       | `Decimal Odds` |
| `--preview-only`          |       | Only scrape visible submarkets (faster, limited data)            | No       | `False`        |
| `--bookies-filter`        |       | Bookmaker filter: `all`, `classic`, or `crypto`                  | No       | `all`          |
| `--period`                |       | Match period to scrape (sport-specific)                          | No       | Sport default  |

**Example Usage:**

```bash
# Retrieve historical odds for the Premier League 2022-2023 season
oddsharvester historic -s football -l england-premier-league --season 2022-2023 -m 1x2 --headless

# Retrieve historical odds for multiple leagues
oddsharvester historic -s football -l england-premier-league,spain-laliga --season 2022-2023 -m 1x2 --headless

# Retrieve historical odds for the current season
oddsharvester historic -s football -l england-premier-league --season current -m 1x2 --headless

# Retrieve historical MLB 2022 season data
oddsharvester historic -s baseball -l usa-mlb --season 2022 -m moneyline --headless

# Scrape only 3 pages of historical data
oddsharvester historic -s football -l england-premier-league --season 2022-2023 -m 1x2 --max-pages 3 --headless

# Save output to CSV format
oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2 -f csv -o premier_league_odds --headless
```

#### **Preview Mode**

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

### **🌐 Environment Variables**

All CLI options can also be configured via environment variables. This is useful for Docker deployments or CI/CD pipelines.

| Environment Variable | CLI Option           | Description                        |
| -------------------- | -------------------- | ---------------------------------- |
| `OH_SPORT`           | `--sport`            | Sport to scrape                    |
| `OH_LEAGUES`         | `--league`           | Comma-separated leagues            |
| `OH_MARKETS`         | `--market`           | Comma-separated markets            |
| `OH_STORAGE`         | `--storage`          | Storage type (local/remote)        |
| `OH_FORMAT`          | `--format`           | Output format (json/csv)           |
| `OH_FILE_PATH`       | `--output`           | Output file path                   |
| `OH_HEADLESS`        | `--headless`         | Run in headless mode               |
| `OH_CONCURRENCY`     | `--concurrency`      | Number of concurrent tasks         |
| `OH_PROXY_URL`       | `--proxy-url`        | Proxy server URL                   |
| `OH_PROXY_USER`      | `--proxy-user`       | Proxy username                     |
| `OH_PROXY_PASS`      | `--proxy-pass`       | Proxy password                     |
| `OH_USER_AGENT`      | `--user-agent`       | Custom browser user agent          |
| `OH_LOCALE`          | `--locale`           | Browser locale                     |
| `OH_TIMEZONE`        | `--timezone`         | Browser timezone ID                |

**Example:**

```bash
export OH_SPORT=football
export OH_HEADLESS=true
export OH_PROXY_URL=http://proxy.example.com:8080

oddsharvester upcoming -d 20250301 -m 1x2
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

   ```bash
   docker run --rm odds-harvester:local python3 -m oddsharvester upcoming -s football -d 20250301 -m 1x2 -o output.json --headless
   ```

   Or using environment variables:

   ```bash
   docker run --rm \
     -e OH_SPORT=football \
     -e OH_HEADLESS=true \
     odds-harvester:local python3 -m oddsharvester upcoming -d 20250301 -m 1x2
   ```

4. **Interactive Mode for Debugging**
   If you need to debug or run commands interactively: `docker run --rm -it odds-harvester:latest /bin/bash`

**Tips**:

- **Volume Mapping**: Use volume mapping to store logs or output data on the host machine.
- **Container Reusability**: Assign a unique container name to avoid conflicts when running multiple instances.

### **☁️ Cloud Deployment**

OddsHarvester can also be deployed on a cloud provider using the **Serverless Framework**, with a Docker image to ensure compatibility with AWS Lambda (Dockerfile will need to be tweaked if you want to deploy on a different cloud provider).

**Why Use a Docker Image?**

1. AWS Lambda's Deployment Size Limit:
   AWS Lambda has a hard limit of 50MB for direct deployment packages, which includes code, dependencies, and assets. Playwright and its browser dependencies far exceed this limit.

2. Playwright's Incompatibility with Lambda Layers:
   Playwright cannot be installed as an AWS Lambda layer because:
   - Its browser dependencies require system libraries that are unavailable in Lambda's standard runtime environment.
   - Packaging these libraries within Lambda layers would exceed the layer size limit.

3. Solution:
   Using a Docker image solves these limitations by bundling the entire runtime environment, including Playwright, its browsers, and all required libraries, into a single package. This ensures a consistent and compatible execution environment.

**Serverless Framework Setup:**

1. **Serverless Configuration**:
   The application includes a `serverless.yaml` file located at the root of the project. This file defines the deployment configuration for a serverless environment. Users can customize the configuration as needed, including:

   - **Provider**: Specify the cloud provider (e.g., AWS).
   - **Region**: Set the desired deployment region (e.g., `eu-west-3`).
   - **Resources**: Update the S3 bucket details or permissions as required.

2. **Docker Integration**:
   The app uses a Docker image (`playwright_python_arm64`) to ensure compatibility with the serverless architecture. The Dockerfile is already included in the project and configured in `serverless.yaml`.
   You'll need to build the image locally (see section above) and push the Docker image to ECR.

3. **Permissions**:
   By default, the app is configured with IAM roles to:

   - Upload (`PutObject`), retrieve (`GetObject`), and delete (`DeleteObject`) files from an S3 bucket.
     Update the `Resource` field in `serverless.yaml` with the ARN of your S3 bucket.

4. **Function Details**:
   - **Function Name**: `scanAndStoreOddsPortalDataV2`
   - **Memory Size**: 2048 MB
   - **Timeout**: 360 seconds
   - **Event Trigger**: Runs automatically every 2 hours (`rate(2 hours)`) via EventBridge.

**Customizing Your Configuration:**
To tailor the serverless deployment for your needs:

- Open the `serverless.yaml` file in the root directory.
- Update the relevant fields:
  - S3 bucket ARN in the IAM policy.
  - Scheduling rate for the EventBridge trigger.
  - Resource limits (e.g., memory size or timeout).

**Deploying to your preferred Cloud provider:**

1. Install the Serverless Framework:
   - Follow the installation guide at [Serverless Framework](https://www.serverless.com/).
2. Deploy the application:
   - Use the `sls deploy` command to deploy the app to your cloud provider.
3. Verify the deployment:
   - Confirm that the function is scheduled correctly and check logs or S3 outputs.

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
