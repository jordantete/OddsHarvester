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

| 🏅 Sport        | 🛒 Supported Markets                                                                               |
| --------------- | -------------------------------------------------------------------------------------------------- |
| ⚽ Football     | `1x2`, `btts`, `double_chance`, `draw_no_bet`, `over/under`, `european_handicap`, `asian_handicap` |
| 🎾 Tennis       | `match_winner`, `total_sets_over/under`, `total_games_over/under`, `asian_handicap`, `exact_score` |
| 🏀 Basketball   | `1x2`, `moneyline`, `asian_handicap`, `over/under`                                                 |
| 🏉 Rugby League | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `over/under`, `handicap`                       |
| 🏉 Rugby Union  | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `over/under`, `handicap`                       |
| 🏒 Ice Hockey   | `1x2`, `home_away`, `double_chance`, `draw_no_bet`, `btts`, `over/under`                           |
| ⚾ Baseball     | `moneyline`, `over/under`                                                                          |

> ⚙️ **Note**: Each sport and its markets are declared in enums inside `sport_market_constants.py`.

#### 🗺️ Leagues & Competitions

Leagues and tournaments are mapped per sport in:
[`sport_league_constants.py`](src/utils/sport_league_constants.py)

You'll find support for:

- 🏆 **Top Football leagues** (Premier League, La Liga, Serie A, etc.)
- 🎾 **Major Tennis tournaments** (ATP, WTA, Grand Slams, etc.)
- 🏀 **Global Basketball leagues** (NBA, EuroLeague, ACB, etc.)
- 🏉 **Major Rugby League competitions** (NRL, Super League, etc.)
- 🏉 **Major Rugby Union competitions** (Six Nations, Rugby Championship, Top 14, etc.)
- 🏒 **Major Ice Hockey leagues** (NHL, KHL, SHL, Liiga, etc.)
- ⚾ **Major Baseball leagues** (MLB, NPB, KBO, etc.)

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
   uv run python src/main.py --help
   ```

By following these steps, you should have **OddsHarvester** set up and ready to use.

## **⚡ Usage**

### **🔧 CLI Commands**

OddsHarvester provides a Command-Line Interface (CLI) to scrape sports betting data from oddsportal.com. Use it to retrieve upcoming match odds, analyze historical data, or store results for further processing. Below are the available commands and their options:

#### **1. Scrape Upcoming Matches**

Retrieve odds and event details for upcoming sports matches.

**Options**:

| 🏷️ Option                   | 📝 Description                                                                                                        | 🔐 Required                                         | 🔧 Default     |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | -------------- |
| `--sport`                   | Specify the sport to scrape (e.g., `football`, `ice-hockey`, `baseball`).                                             | ✅                                                  | None           |
| `--date`                    | Date for matches in `YYYYMMDD` format (e.g., `20250227`).                                                             | ✅ (unless `--match_links` or `--leagues` provided) | None           |
| `--leagues`                 | Comma-separated leagues to scrape (e.g., `england-premier-league,spain-laliga`).                                      | ❌                                                  | None           |
| `--markets`                 | Comma-separated betting markets (e.g., `1x2,btts`).                                                                   | ❌                                                  | None           |
| `--storage`                 | Save data locally or to a remote S3 bucket (`local` or `remote`).                                                     | ❌                                                  | `local`        |
| `--file_path`               | File path to save data locally (e.g., `output.json`).                                                                 | ❌                                                  | None           |
| `--format`                  | Format for saving local data (`json` or `csv`).                                                                       | ❌                                                  | None           |
| `--headless`                | Run the browser in headless mode (`True` or `False`).                                                                 | ❌                                                  | `False`        |
| `--save_logs`               | Save logs for debugging purposes (`True` or `False`).                                                                 | ❌                                                  | `False`        |
| `--proxies`                 | List of proxies in `"server user pass"` format. Multiple proxies supported.                                           | ❌                                                  | None           |
| `--browser_user_agent`      | Custom user agent string for browser requests.                                                                        | ❌                                                  | None           |
| `--browser_locale_timezone` | Browser locale timezone (e.g., `fr-BE`).                                                                              | ❌                                                  | None           |
| `--browser_timezone_id`     | Browser timezone ID (e.g., `Europe/Brussels`).                                                                        | ❌                                                  | None           |
| `--match_links`             | List of specific match links to scrape (overrides other filters).                                                     | ❌                                                  | None           |
| `--target_bookmaker`        | Filter scraping for a specific bookmaker (e.g., `Betclic.fr`).                                                        | ❌                                                  | None           |
| `--scrape_odds_history`     | Include odds movement history by hovering modals.                                                                     | ❌                                                  | `False`        |
| `--odds_format`             | Odds format to display (`Decimal Odds`, `Fractional Odds`, `Money Line Odds`, `Hong Kong Odds`).                      | ❌                                                  | `Decimal Odds` |
| `--concurrency_tasks`       | Number of concurrent tasks for scraping.                                                                              | ❌                                                  | `3`            |
| `--preview_submarkets_only` | Only scrape average odds from visible submarkets without loading individual bookmaker details (faster, limited data). | ❌                                                  | `False`        |

#### **📌 Important Notes:**

- If both `--leagues` and `--date` are provided, the scraper **will only consider the leagues**, meaning **all upcoming matches for those leagues will be scraped**, regardless of the `--date` argument.
- **If `--match_links` is provided, it overrides `--sport`, `--date`, and `--leagues`, and only the specified match links will be scraped.**
- **All match links must belong to the same sport** when using `--match_links`.
- **For best results, ensure the proxy's region matches the `BROWSER_LOCALE_TIMEZONE` and `BROWSER_TIMEZONE_ID` settings.**

#### **Example Usage:**

- **Retrieve upcoming football matches for January 1, 2025, and save results locally:**

`uv run python src/main.py scrape_upcoming --sport football --markets 1x2 --date 20250101 --headless`

- **Scrapes English Premier League matches with odds for 1x2 and Both Teams to Score (BTTS):**

`uv run python src/main.py scrape_upcoming --sport football --leagues england-premier-league --markets 1x2,btts --storage local --headless`

- **Scrapes multiple leagues at once:**

`uv run python src/main.py scrape_upcoming --sport football --leagues england-premier-league,spain-laliga,italy-serie-a --markets 1x2,btts --storage local --headless`

- **Scrapes baseball matches using a rotating proxy setup:**

`uv run python src/main.py scrape_upcoming --sport baseball --date 20250227 --markets moneyline --proxies "http://proxy1.com:8080 user1 pass1" "http://proxy2.com:8080 user2 pass2" --headless`

- **Scrapes football matches in preview mode (average odds only, faster):**

`uv run python src/main.py scrape_upcoming --sport football --date 20250101 --markets over_under_2_5 --preview_submarkets_only --headless`

#### **2. Scrape Historical Odds**

Retrieve historical odds and results for analytical purposes.

**Options**:

| 🏷️ Option                   | 📝 Description                                                                                                        | 🔐 Required | 🔧 Default     |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------- | -------------- |
| `--sport`                   | Specify the sport to scrape (e.g., `football`, `ice-hockey`, `baseball`).                                             | ✅          | None           |
| `--leagues`                 | Comma-separated leagues to scrape (e.g., `england-premier-league,spain-laliga`).                                      | ✅          | None           |
| `--season`                  | Target season in `YYYY`, `YYYY-YYYY` format (e.g., `2022` or `2022-2023`), or `current` for the current season.       | ✅          | None           |
| `--markets`                 | Comma-separated betting markets (e.g., `1x2,btts`).                                                                   | ❌          | None           |
| `--storage`                 | Save data locally or to a remote S3 bucket (`local` or `remote`).                                                     | ❌          | `local`        |
| `--file_path`               | File path to save data locally (e.g., `output.json`).                                                                 | ❌          | None           |
| `--format`                  | Format for saving local data (`json` or `csv`).                                                                       | ❌          | None           |
| `--max_pages`               | Maximum number of pages to scrape.                                                                                    | ❌          | None           |
| `--headless`                | Run the browser in headless mode (`True` or `False`).                                                                 | ❌          | `False`        |
| `--save_logs`               | Save logs for debugging purposes (`True` or `False`).                                                                 | ❌          | `False`        |
| `--proxies`                 | List of proxies in `"server user pass"` format. Multiple proxies supported.                                           | ❌          | None           |
| `--browser_user_agent`      | Custom user agent string for browser requests.                                                                        | ❌          | None           |
| `--browser_locale_timezone` | Browser locale timezone (e.g., `fr-BE`).                                                                              | ❌          | None           |
| `--browser_timezone_id`     | Browser timezone ID (e.g., `Europe/Brussels`).                                                                        | ❌          | None           |
| `--match_links`             | List of specific match links to scrape (overrides other filters).                                                     | ❌          | None           |
| `--target_bookmaker`        | Filter scraping for a specific bookmaker (e.g., `Betclic.fr`).                                                        | ❌          | None           |
| `--scrape_odds_history`     | Include odds movement history by hovering modals.                                                                     | ❌          | `False`        |
| `--odds_format`             | Odds format to display (`Decimal Odds`, `Fractional Odds`, `Money Line Odds`, `Hong Kong Odds`).                      | ❌          | `Decimal Odds` |
| `--concurrency_tasks`       | Number of concurrent tasks for scraping.                                                                              | ❌          | `3`            |
| `--preview_submarkets_only` | Only scrape average odds from visible submarkets without loading individual bookmaker details (faster, limited data). | ❌          | `False`        |

#### **Example Usage:**

- **Retrieve historical odds for the Premier League's 2022-2023 season:**

`uv run python src/main.py scrape_historic --sport football --leagues england-premier-league --season 2022-2023 --markets 1x2 --headless`

- **Retrieve historical odds for multiple leagues at once:**

`uv run python src/main.py scrape_historic --sport football --leagues england-premier-league,spain-laliga,italy-serie-a --season 2022-2023 --markets 1x2 --headless`

- **Retrieve historical odds for the current season of Premier League:**

`uv run python src/main.py scrape_historic --sport football --leagues england-premier-league --season current --markets 1x2 --headless`

- **Retrieve historical MLB 2022 season data:**

`uv run python src/main.py scrape_historic --sport baseball --leagues usa-mlb --season 2022 --markets moneyline --headless`

- **Scrapes only 3 pages of historical odds data:**

`uv run python src/main.py scrape_historic --sport football --leagues england-premier-league --season 2022-2023 --markets 1x2 --max_pages 3 --headless`

- **Scrapes historical odds in preview mode (average odds only, faster):**

`uv run python src/main.py scrape_historic --sport football --leagues england-premier-league --season 2022-2023 --markets over_under_2_5 --preview_submarkets_only --headless`

#### **📌 Preview Mode**

The `--preview_submarkets_only` flag enables a faster scraping mode that extracts only average odds from visible submarkets without loading individual bookmaker details. This mode is useful for:

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

#### **📌 Running the Help Command:**

To display all available CLI commands and options, run:

`uv run python src/main.py --help`

### **🐳 Running Inside a Docker Container**

OddsHarvester is compatible with Docker, allowing you to run the application seamlessly in a containerized environment.

**Steps to Run with Docker:**

1. **Ensure Docker is Installed**
   Make sure Docker is installed and running on your system. Visit [Docker's official website](https://www.docker.com/) for installation instructions specific to your operating system.

2. **Build the Docker Image**
   Navigate to the project's root directory, where the `Dockerfile` is located. Build the Docker image using the appropriate Docker build command.
   Assign a name to the image, such as `odds-harvester`: `docker build -t odds-harvester:local --target local-dev .`

3. **Run the Container**
   Start a Docker container based on the built image. Map the necessary ports if required and specify any volumes to persist data. Pass any CLI arguments (e.g., `scrape_upcoming`) as part of the Docker run command:
   `docker run --rm odds-harvester:latest python3 -m main scrape_upcoming --sport football --date 20250125 --markets 1x2 --storage local --file_path output.json --headless`

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
   • Its browser dependencies require system libraries that are unavailable in Lambda's standard runtime environment.
   • Packaging these libraries within Lambda layers would exceed the layer size limit.

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

**Deploying to your prefered Cloud provider:**

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
