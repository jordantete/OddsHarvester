"""Output handling shared by the CLI commands."""

from datetime import UTC, datetime
import logging

import click

from oddsharvester.core.scrape_result import ErrorType, ScrapeResult
from oddsharvester.storage.local_data_storage import LocalDataStorage
from oddsharvester.storage.storage_format import StorageFormat
from oddsharvester.storage.storage_manager import store_data

logger = logging.getLogger(__name__)

_EXTENSIONS = (".json", ".csv")


def write_output(data: list[dict], kwargs: dict, storage, storage_format) -> bool:
    """Store the batch; when that fails, save it to a local JSON fallback and say where. False on failure."""
    file_path = kwargs.get("file_path")
    fmt = storage_format.value if storage_format else "json"
    if store_data(
        storage_type=storage.value if storage else "local",
        data=data,
        storage_format=fmt,
        file_path=file_path,
        append=kwargs.get("append", False),
    ):
        return True

    target = _target_path(file_path, fmt)
    fallback = _fallback_path(file_path)
    try:
        LocalDataStorage().save_data(data=data, file_path=fallback, storage_format=StorageFormat.JSON.value)
    except Exception as e:
        logger.error(f"Fallback write to {fallback} failed: {e}", exc_info=True)
        click.echo(
            f"Could not write the output to {target} (see the error above), and saving the {len(data)} records "
            f"to {fallback} failed too: {e}",
            err=True,
        )
        return False

    click.echo(
        f"Could not write the output to {target} (see the error above). "
        f"The {len(data)} records were saved to {fallback} instead.",
        err=True,
    )
    return False


def _target_path(file_path: str | None, fmt: str) -> str:
    target = file_path or LocalDataStorage().default_file_path
    return target if target.endswith(f".{fmt}") else f"{target}.{fmt}"


def _fallback_path(file_path: str | None) -> str:
    base = file_path or LocalDataStorage().default_file_path
    for extension in _EXTENSIONS:
        if base.endswith(extension):
            base = base[: -len(extension)]
            break
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}.unsaved-{stamp}.json"


def format_combo_summary(combo_stats: list[dict], links_only: bool) -> str:
    """Render the per-combo breakdown shown at the end of a multi-combo run."""
    unit = "links" if links_only else "matches"
    labels = [f"{c['league']} {c['season']}".strip() if c["season"] else c["league"] for c in combo_stats]
    width = max(len(label) for label in labels)

    lines = [f"Collected {unit} across {len(combo_stats)} combos:"]
    empty = errored = 0

    for label, combo in zip(labels, combo_stats, strict=True):
        if combo["errored"]:
            lines.append(f"  {label:<{width}}  error")
            errored += 1
        else:
            lines.append(f"  {label:<{width}}  {combo['successful']}")
            if combo["successful"] == 0:
                empty += 1

    if empty:
        lines.append(f"{empty} combo(s) returned nothing.")
    if errored:
        lines.append(f"{errored} combo(s) errored.")

    return "\n".join(lines)


def report_incomplete_collection(result: ScrapeResult) -> bool:
    """Say so when listing pages or whole combos failed: their matches were never discovered."""
    listing_failures = [f for f in result.failed if f.error_type is ErrorType.LISTING_PAGE]
    if not listing_failures:
        return False

    logger.error(f"Incomplete collection: {len(listing_failures)} listing page(s) failed.")
    click.echo(
        f"Incomplete collection: {len(listing_failures)} listing page(s) failed, so an unknown "
        f"number of matches were never discovered. The partial data was kept.",
        err=True,
    )
    return True
