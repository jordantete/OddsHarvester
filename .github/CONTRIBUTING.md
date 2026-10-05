# Contributing

Thanks for your interest in contributing to **OddsHarvester**!

## Getting Started

1. Fork the repository and clone your fork.
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Create a branch for your changes:
   ```bash
   git checkout -b my-feature
   ```

## Development Workflow

### Running the scraper

```bash
# Scrape today's upcoming matches
uv run oddsharvester upcoming --sport football --date $(date +%Y%m%d) --market 1x2

# Scrape historic matches
uv run oddsharvester historic --sport football --league england-premier-league --season 2022-2023 --market 1x2
```

### Linting & Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) (120-char line length, Python 3.12). Pre-commit hooks are configured — install them with:

```bash
uv run pre-commit install
```

You can also run them manually:

```bash
uv run pre-commit run --all-files
```

### Running Tests

```bash
# Unit tests
uv run pytest tests/ -q --ignore=tests/integration/

# Integration tests (replay the recorded HAR files, no network)
uv run pytest tests/integration/ -q -m integration

# Integration tests against the live site
uv run pytest tests/integration/ -q -m integration --live

# Unit tests with coverage
uv run pytest --cov=src/oddsharvester --cov-report=term --ignore=tests/integration/
```

## Pull Requests

- Keep PRs focused on a single change.
- Add or update tests for any new behavior.
- Make sure all tests pass and pre-commit hooks are green before opening a PR.
- Fill out the [PR template](PULL_REQUEST_TEMPLATE.md) when submitting.

## Reporting Issues

Open an issue describing the problem, including steps to reproduce, expected behavior, and your environment (OS, Python version, etc.).
