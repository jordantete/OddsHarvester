"""Fetch a few currently-listed free HTTP proxies for MANUAL smoke testing only.

Free proxies are volatile and unauthenticated; never use this in the test suite or
in production. Prints `--proxy-url http://host:port` lines ready to paste.

Usage: uv run python scripts/fetch_free_proxies.py --limit 5
"""

import argparse
import urllib.request

PROXYSCRAPE_URL = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all"


def fetch(limit: int) -> list[str]:
    with urllib.request.urlopen(PROXYSCRAPE_URL, timeout=20) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8", errors="ignore")
    proxies = [line.strip() for line in raw.splitlines() if line.strip()]
    return proxies[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    for hostport in fetch(args.limit):
        print(f"--proxy-url http://{hostport}")


if __name__ == "__main__":
    main()
