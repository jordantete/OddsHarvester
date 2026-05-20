# Single-stage image for running the OddsHarvester CLI in a container.
#
# Base image tag MUST stay aligned with the `playwright` version locked in
# uv.lock / pinned in pyproject.toml. The MS Playwright image ships the
# matching Chromium build; a mismatch breaks scraping at runtime.
# Current: playwright 1.57.0  ->  base tag v1.57.0-noble
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

# Install uv globally
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy application files
COPY src /app/src
COPY pyproject.toml uv.lock README.md LICENSE.txt /app/

# Install runtime dependencies (the `dev` extra is not installed)
RUN uv sync --frozen

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# CLI entrypoint: lets `docker run odds-harvester upcoming ...` append CLI
# args directly. Playwright runs with --headless from the CLI, so no virtual
# display (xvfb) is required — wrapping the entrypoint with xvfb-run hangs
# the container on macOS/colima before python ever starts.
ENTRYPOINT ["python3", "-m", "oddsharvester"]
