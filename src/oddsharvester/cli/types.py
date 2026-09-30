"""Custom Click parameter types for OddsHarvester CLI."""

import importlib.util
import os

import click

from oddsharvester.storage.remote_data_storage import s3_bucket
from oddsharvester.storage.storage_format import StorageFormat
from oddsharvester.storage.storage_type import StorageType
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.odds_format_enum import OddsFormat
from oddsharvester.utils.sport_market_constants import Sport


class SportType(click.ParamType):
    """Custom Click type for Sport enum."""

    name = "sport"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            return Sport(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in Sport)
            self.fail(f"Invalid sport '{value}'. Valid options: {valid}", param, ctx)


class StorageTypeType(click.ParamType):
    """Custom Click type for StorageType enum; checks what remote storage needs before any scraping."""

    name = "storage_type"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            storage = StorageType(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in StorageType)
            self.fail(f"Invalid storage type '{value}'. Valid options: {valid}", param, ctx)

        if storage is StorageType.REMOTE:
            problems = []
            if not s3_bucket():
                state = "is not set" if os.environ.get("OH_S3_BUCKET") is None else "is empty"
                problems.append(f"OH_S3_BUCKET {state}. Name the bucket to upload to: export OH_S3_BUCKET=<bucket>")
            if importlib.util.find_spec("boto3") is None:
                problems.append("boto3 is not installed. Install the S3 extra: pip install 'oddsharvester[s3]'")
            if problems:
                self.fail("\n".join(problems), param, ctx)
        return storage


class StorageFormatType(click.ParamType):
    """Custom Click type for StorageFormat enum."""

    name = "storage_format"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            return StorageFormat(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in StorageFormat)
            self.fail(f"Invalid storage format '{value}'. Valid options: {valid}", param, ctx)


class BookiesFilterType(click.ParamType):
    """Custom Click type for BookiesFilter enum."""

    name = "bookies_filter"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            return BookiesFilter(value.lower())
        except ValueError:
            valid = ", ".join(f.value for f in BookiesFilter)
            self.fail(f"Invalid bookies filter '{value}'. Valid options: {valid}", param, ctx)


class OddsFormatType(click.ParamType):
    """Custom Click type for OddsFormat enum."""

    name = "odds_format"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            return OddsFormat(value)
        except ValueError:
            valid = ", ".join(f.value for f in OddsFormat)
            self.fail(f"Invalid odds format '{value}'. Valid options: {valid}", param, ctx)


class CommaSeparatedList(click.ParamType):
    """Custom Click type for comma-separated lists."""

    name = "list"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]


SPORT = SportType()
STORAGE_TYPE = StorageTypeType()
STORAGE_FORMAT = StorageFormatType()
BOOKIES_FILTER = BookiesFilterType()
ODDS_FORMAT = OddsFormatType()
COMMA_LIST = CommaSeparatedList()
