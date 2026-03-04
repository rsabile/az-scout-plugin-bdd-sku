"""Input validation helpers for the v1 API.

Centralises limit parsing, ISO datetime parsing, and enum validation
so that route handlers stay thin.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum

DEFAULT_LIMIT = 1000
MIN_LIMIT = 1
MAX_LIMIT = 5000


class Bucket(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


class Agg(StrEnum):
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class Sample(StrEnum):
    RAW = "raw"
    HOURLY = "hourly"
    DAILY = "daily"


class ValidationError(ValueError):
    """Raised when user input does not pass validation."""


def parse_limit(value: int | None, *, default: int = DEFAULT_LIMIT) -> int:
    """Return a validated limit or *default*.

    Raises ``ValidationError`` for out-of-range values.
    """
    if value is None:
        return default
    if value < MIN_LIMIT or value > MAX_LIMIT:
        raise ValidationError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}, got {value}")
    return value


def parse_iso_dt(value: str | None, *, param_name: str = "datetime") -> datetime | None:
    """Parse an ISO 8601 string to a timezone-aware ``datetime``.

    Returns ``None`` when *value* is ``None`` or empty.
    Raises ``ValidationError`` on malformed input.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Invalid ISO datetime for '{param_name}': {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def validate_bucket(value: str) -> str:
    """Validate and return a bucket value (hour/day/week).

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return Bucket(value.lower()).value
    except ValueError as exc:
        raise ValidationError(f"Invalid bucket '{value}', must be one of: hour, day, week") from exc


def validate_agg(value: str) -> str:
    """Validate and return an aggregation function name.

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return Agg(value.lower()).value
    except ValueError as exc:
        raise ValidationError(f"Invalid agg '{value}', must be one of: avg, min, max") from exc


def validate_sample(value: str) -> str:
    """Validate and return a sample mode.

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return Sample(value.lower()).value
    except ValueError as exc:
        raise ValidationError(
            f"Invalid sample '{value}', must be one of: raw, hourly, daily"
        ) from exc


# ------------------------------------------------------------------
# Pricing summary validators
# ------------------------------------------------------------------


class PriceType(StrEnum):
    RETAIL = "retail"
    SPOT = "spot"


class PricingBucket(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class PricingMetric(StrEnum):
    AVG = "avg_price"
    MEDIAN = "median_price"
    MIN = "min_price"
    MAX = "max_price"
    P10 = "p10_price"
    P25 = "p25_price"
    P75 = "p75_price"
    P90 = "p90_price"


# Map user-facing short names to column names
_METRIC_ALIASES: dict[str, str] = {
    "avg": "avg_price",
    "median": "median_price",
    "min": "min_price",
    "max": "max_price",
    "p10": "p10_price",
    "p25": "p25_price",
    "p75": "p75_price",
    "p90": "p90_price",
}


def validate_price_type(value: str) -> str:
    """Validate and return a price type (retail/spot).

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return PriceType(value.lower()).value
    except ValueError as exc:
        raise ValidationError(f"Invalid priceType '{value}', must be one of: retail, spot") from exc


def validate_pricing_bucket(value: str) -> str:
    """Validate and return a pricing bucket (day/week/month).

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return PricingBucket(value.lower()).value
    except ValueError as exc:
        raise ValidationError(
            f"Invalid bucket '{value}', must be one of: day, week, month"
        ) from exc


def validate_metric(value: str) -> str:
    """Validate and return a metric column name.

    Accepts both short names (``avg``, ``median``) and full column names
    (``avg_price``, ``median_price``).  Raises ``ValidationError`` on invalid input.
    """
    lower = value.lower()
    if lower in _METRIC_ALIASES:
        return _METRIC_ALIASES[lower]
    try:
        return PricingMetric(lower).value
    except ValueError as exc:
        allowed = ", ".join(sorted(_METRIC_ALIASES.keys()))
        raise ValidationError(f"Invalid metric '{value}', must be one of: {allowed}") from exc


# ------------------------------------------------------------------
# Job / log validators
# ------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class JobStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class JobDataset(StrEnum):
    AZURE_PRICING = "azure_pricing"
    AZURE_SPOT = "azure_spot"
    SKU_MAPPER = "sku_mapper"
    PRICE_AGGREGATOR = "price_aggregator"


class LogLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def validate_uuid(value: str) -> str:
    """Validate UUID format. Raises ``ValidationError`` on invalid input."""
    if not _UUID_RE.match(value):
        raise ValidationError(f"Invalid UUID: {value}")
    return value


def validate_job_status(value: str) -> str:
    """Validate and return a job status value.

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return JobStatus(value.lower()).value
    except ValueError as exc:
        raise ValidationError(
            f"Invalid status '{value}', must be one of: running, ok, error"
        ) from exc


def validate_job_dataset(value: str) -> str:
    """Validate and return a job dataset value.

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return JobDataset(value.lower()).value
    except ValueError as exc:
        allowed = ", ".join(d.value for d in JobDataset)
        raise ValidationError(f"Invalid dataset '{value}', must be one of: {allowed}") from exc


def validate_log_level(value: str) -> str:
    """Validate and return a log level value.

    Raises ``ValidationError`` on invalid input.
    """
    try:
        return LogLevel(value.lower()).value
    except ValueError as exc:
        raise ValidationError(
            f"Invalid level '{value}', must be one of: info, warning, error"
        ) from exc
