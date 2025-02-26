# **OddsHarvester**

OddsHarvester is an application designed to scrape and process sports betting odds and match data from **oddsportal.com** website. 


## **📖 Table of Contents**

1. [✨ Features](#-features)
2. [🚀 Roadmap](#-roadmap)
3. [🛠️ Local Installation](#-local-installation)
4. [⚡ Usage](#-usage)
    - [🔧 CLI Commands](#cli-commands)
    - [🐳 Running Inside a Docker Container](#-running-inside-a-docker-container)
    - [☁️ Cloud Deployment](#-cloud-deployment)
5. [⚙️ Configuration](#-configuration)
6. [🤝 Contributing](#-contributing)
7. [📜 License](#-license)
8. [💬 Feedback](#-feedback)
9. [❗ Disclaimer](#-disclaimer)


## **✨ Features**

- **📅 Scrape Upcoming Matches**: Fetch odds and event details for upcoming sports matches.  
- **📊 Scrape Historical Odds**: Retrieve historical odds and match results for analytical purposes.  
- **🔍 Advanced Parsing**: Extract structured data, including match dates, team names, scores, and venue details.  
- **💾 Flexible Storage**: Store scraped data in JSON or CSV locally, or upload it directly to a remote S3 bucket.
- **🐳 Docker Compatibility**: Designed to work seamlessly inside Docker containers with minimal setup. 
- **🕵️ Proxy Support**: Route web requests through SOCKS/HTTP proxies for enhanced anonymity, geolocation bypass, and anti-blocking measures.


## **🚀 Roadmap**

Here’s what’s coming next in **OddsHarvester**:

- **Multi-Sport Expansion**: Add support for more sports beyond football and tennis (e.g., basketball, baseball).  
- **Odds Movement Tracking**: Analyze how odds evolve over time to detect market trends.  

💡 **Have ideas?** Open an issue or contribute directly to the repository! 🚀  

### **Current Support**

OddsHarvester currently supports multiple sports for scraping, with their respective betting markets and leagues managed in dedicated configuration files.

- **Supported Sports**  
  The list of available sports is maintained in the `Sport` enum inside the [`sport_market_constants.py`](src/utils/sport_market_constants.py) file.

- **Betting Markets**  
  Each sport has its own set of supported betting markets, defined as Enums in the [`sport_market_constants.py`](src/utils/sport_market_constants.py) file.

- **Leagues & Competitions**  
  The available leagues for each sport are mapped in the [`sport_league_constants.py`](src/utils/sport_league_constants.py) file.


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
      - `pvython3 -m venv .venv`

     - On Unix/MacOS:
       `source venv/bin/activate`

     - On Windows:  
       `venv\Scripts\activate`

   - **Install dependencies with pip**: Use pip with the `--use-pep517` flag to install directly from the `pyproject.toml` file: 
       `pip install . --use-pep517`.

   - **Or install dependencies with poetry**: If you prefer poetry for dependency management:
         `poetry install`

4. **Verify Installation**: 

   Ensure all dependencies are installed and Playwright is set up by running the following command:  
   ```bash
   cd src
   python main.py --help
   ```

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
   Assign a name to the image, such as `odds-harvester`: `docker build -t odds-harvester:local --target local-dev .`

3. **Run the Container**  
   Start a Docker container based on the built image. Map the necessary ports if required and specify any volumes to persist data. Pass any CLI arguments (e.g., `scrape_upcoming`) as part of the Docker run command: 
   `docker run --rm odds-harvester:latest python3 -m main scrape_upcoming --sport football --date 20250125 --markets 1x2 --storage local --file_path output.json --headless`

4.	**Interactive Mode for Debugging**
   If you need to debug or run commands interactively: `docker run --rm -it odds-harvester:latest /bin/bash`

**Tips**:
- **Volume Mapping**: Use volume mapping to store logs or output data on the host machine.  
- **Proxy Configuration**: Ensure your `constants.py` file is configured correctly if you’re using proxies or targeting specific regions.  
- **Container Reusability**: Assign a unique container name to avoid conflicts when running multiple instances.


### **☁️ Cloud Deployment**

OddsHarvester can also be deployed on a cloud provider using the **Serverless Framework**, with a Docker image to ensure compatibility with AWS Lambda (Dockerfile will need to be tweaked if you want to deploy on a different cloud provider).

**Why Use a Docker Image?**

1.	AWS Lambda’s Deployment Size Limit:
   AWS Lambda has a hard limit of 50MB for direct deployment packages, which includes code, dependencies, and assets. Playwright and its browser dependencies far exceed this limit.

2.	Playwright’s Incompatibility with Lambda Layers:
   Playwright cannot be installed as an AWS Lambda layer because:
      •	Its browser dependencies require system libraries that are unavailable in Lambda’s standard runtime environment.
      •	Packaging these libraries within Lambda layers would exceed the layer size limit.

3.	Solution:
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


## **⚙️ Configuration**

### Constants

OddsHarvester uses a [`constants.py`](src/utils/constants.py) file to define important parameters for browser configuration and scraping behavior. Users can customize these parameters directly in the file to suit their needs. Key configurable constants include:

- **`BROWSER_USER_AGENT`**: Define the user agent string used by the browser to simulate specific devices or browsers.
- **`BROWSER_LOCALE_TIMEZONE`**: Set the locale for the browser (e.g., `"en-US"`).
- **`BROWSER_TIMEZONE_ID`**: Specify the browser's timezone (e.g., `"Europe/Paris"`).
- **`ODDS_FORMAT`**: Configure the desired odds format (e.g., `Decimal Odds`, `Fractional Odds`).
- **`SCRAPE_CONCURRENCY_TASKS`**: Adjust the number of concurrent tasks the scraper can handle. Controls how many pages or tasks are processed simultaneously. Increasing this value can speed up scraping but may increase the risk of being blocked by the target website. Use cautiously based on your network and system capabilities.

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
