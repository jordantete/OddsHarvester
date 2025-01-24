# **OddsHarvester**

OddsHarvester is an application designed to scrape and process sports betting odds and match data from **oddsportal.com** website. 

## **✨ Features**

- **📅 Scrape Upcoming Matches**: Fetch odds and event details for upcoming sports matches.  
- **📊 Scrape Historical Odds**: Retrieve historical odds and results for analytical purposes.  
- **🔍 Advanced Parsing**: Extract structured data, including match dates, team names, scores, and venue details.  
- **💾 Flexible Storage**: Save data locally as JSON or CSV, or send it to a remote S3 bucket.
- **🐳 Docker Compatibility**: Detect and run seamlessly inside Docker containers.  
- **🕵️ Proxy Support**: Route web requests through SOCKS/HTTP proxies for anonymity and geolocation.


## **🚀 Roadmap**

Here’s a list of upcoming features and improvements planned for OddsHarvester:

- **Expanded Football Markets**  
  Add support for additional football betting markets, such as: Half-Time/Full-Time, Draw No Bet, European Handicap.

- **Support for More Sports**  
  Extend the application's functionality to include more sports by updating the `SUPPORTED_SPORTS` list.

- **Scrape the Evolution of Odds Over Time**  
  Enable analysis of how odds change over time (historical data only).

  - **Increase code coverage**  
  Add more unit tests to cover the core components of the app.

💡 Suggestions for new features or improvements are always welcome! Feel free to open an issue or contribute directly to the repository.

### **Current Support**

OddsHarvester currently supports **football** as the only sport for scraping, with the following betting markets available:

- **1x2**: Full-time 1X2 odds  
- **Over/Under Goals**:  
  - Over/Under 1.5 goals  
  - Over/Under 2.5 goals  
  - Over/Under 3.5 goals  
  - Over/Under 4.5 goals  
- **BTTS**: Both Teams to Score  
- **Double Chance**: Double chance odds  

These markets are defined in the `SUPPORTED_MARKETS` section of the `constants.py` file.


## **📖 Table of Contents**

1. [🎯 Features](#-features)
2. [🛠️ Local Installation](#-local-installation)
3. [⚡ Usage](#-usage)
    [🔧 CLI Commands](#cli-commands)
    [🐳 Running Inside a Docker Container](#running-inside-a-docker-container)
4. [⚙️ Configuration](#-configuration)
5. [🤝 Contributing](#-contributing)
6. [📜 License](#-license)
7. [💬 Feedback](#-feedback)
8. [❗ Disclaimer](#-disclaimer)


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
   uv setup
   ```

3. **Manual Setup (Optional)**:

   If you prefer to set up manually, follow these steps:

   - **Create a virtual environment**: Use Python's `venv` module to create an isolated environment for the project. Activate it depending on your operating system:

     - On Unix/MacOS:  
       `source venv/bin/activate`
     - On Windows:  
       `venv\Scripts\activate`

   - **Install dependencies**: Install the required Python packages:  
       `pip install -r requirements.txt`.

   - **Set up Playwright**: 
        Install Playwright and its browser dependencies:  
       `playwright install`.
       
       Alternatively, if you'll only make use of one browser (here chromium for instance):
       `playwright install chromium`.

4. **Verify Installation**: 

   Ensure all dependencies are installed and Playwright is set up by running the following command:  
   `python main.py --help`.

By following these steps, you should have **OddsHarvester** set up and ready to use.


## **⚡ Usage**

### **🔧 CLI Commands**

OddsHarvester provides a Command-Line Interface (CLI) to scrape sports betting data from oddsportal.com. Use it to retrieve upcoming match odds, analyze historical data, or store results for further processing. Below are the available commands and their options:

#### **1. Scrape Upcoming Matches**
Retrieve odds and event details for upcoming sports matches.

**Options**:

| 🏷️ Option       | 📝 Description                                                 | 🔐 Required  | 🔧 Default  |
|----------------|-----------------------------------------------------------------|--------------|-------------|
| `--sport`     | Specify the sport to scrape (e.g., `football`).                  | ✅           | None        |
| `--date`      | Date for matches in `YYYY-MM-DD` format.                         | ✅           | None        |
| `--markets`   | Comma-separated betting markets (e.g., `1x2,btts`).              | ❌           | `1x2`       |
| `--storage`   | Save data locally or to a remote S3 bucket (`local` or `remote`).| ❌           | `local`     |
| `--headless`  | Run the browser in headless mode (`True` or `False`).            | ❌           | `False`     |
| `--save_logs` | Save logs for debugging purposes (`True` or `False`).            | ❌           | `False`     |

**Example**:
Retrieve upcoming football matches for January 1, 2025, and save results locally:

`python main.py scrape_upcoming –sport football –date 2025-01-01`


#### **2. Scrape Historical Odds**
Retrieve historical odds and results for analytical purposes.

**Options**:

| 🏷️ Option       | 📝 Description                                                 | 🔐 Required  | 🔧 Default  |
|----------------|-----------------------------------------------------------------|--------------|-------------|
| `--league`    | Target league (e.g., `premier-league`).                          | ✅           | None        |
| `--season`    | Target season in `YYYY-YYYY` format (e.g., `2022-2023`).         | ✅           | None        |
| `--markets`   | Comma-separated betting markets (e.g., `1x2`).                   | ❌           | `1x2`       |
| `--storage`   | Save data locally or to a remote S3 bucket (`local` or `remote`).| ❌           | `local`     |

**Example**:
Retrieve historical odds for the Premier League's 2022-2023 season:

`python main.py scrape_historic –league premier-league –season 2022-2023`


### **🐳 Running Inside a Docker Container**

OddsHarvester is compatible with Docker, allowing you to run the application seamlessly in a containerized environment.

**Steps to Run with Docker:**

1. **Ensure Docker is Installed**  
   Make sure Docker is installed and running on your system. Visit [Docker's official website](https://www.docker.com/) for installation instructions specific to your operating system.

2. **Build the Docker Image**  
   Navigate to the project's root directory, where the `Dockerfile` is located. Build the Docker image using the appropriate Docker build command.  
   Assign a name to the image, such as `odds-harvester`.

3. **Run the Container**  
   Start a Docker container based on the built image. Map the necessary ports if required and specify any volumes to persist data. Pass any CLI arguments (e.g., `scrape_upcoming`) as part of the Docker run command.

**Tips**:
- Use volume mapping to store logs or output data on the host machine.
- Ensure your `constants.py` file is configured correctly if you're using proxies or targeting specific regions.


## **⚙️ Configuration**

### Constants

OddsHarvester uses a `constants.py` file to define important parameters for browser configuration and scraping behavior. Users can customize these parameters directly in the file to suit their needs. Key configurable constants include:

- **`BROWSER_USER_AGENT`**: Define the user agent string used by the browser to simulate specific devices or browsers.
- **`BROWSER_LOCALE_TIMEZONE`**: Set the locale for the browser (e.g., `"en-US"`).
- **`BROWSER_TIMEZONE_ID`**: Specify the browser's timezone (e.g., `"Europe/Paris"`).
- **`ODDS_FORMAT`**: Configure the desired odds format (e.g., `Decimal Odds`, `Fractional Odds`).

To modify these values, locate the `constants.py` file in the `utils` folder and edit the parameters as needed.

### Proxy Configuration

OddsPortal uses geo-targeting to serve different content based on your location. To access specific region-restricted data, using a proxy server is highly recommended. For best results:
- Ensure the proxy’s region matches the `BROWSER_LOCALE_TIMEZONE` and `BROWSER_TIMEZONE_ID` settings.

To configure a proxy, update the `initialize_and_start_playwright` method in the `main.py` file. Pass your proxy details as a dictionary to the `proxy` parameter. Example configuration:

```python
await scraper.initialize_and_start_playwright(
    is_webdriver_headless=True,
    proxy={
        "server": "http://proxy-server:8080",
        "username": "proxy_user",
        "password": "proxy_password"
    }
)
```


## **🤝 Contributing**

Contributions are welcome! If you have ideas, improvements, or bug fixes, feel free to submit an issue or a pull request. Please ensure that your contributions follow the project’s coding standards and include clear descriptions for any changes.


## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE.txt) file for more details.


## **💬 Feedback**

Have any questions or feedback? Feel free to reach out via the issues tab on GitHub. We’d love to hear from you!

## **❗ Disclaimer**

This package is intended for educational purposes only and not for any commercial use in any way. The author is not affiliated with or endorsed by the oddsportal.com website. Use this application responsibly and ensure compliance with the terms of service of oddsportal.com and any applicable laws in your jurisdiction.
