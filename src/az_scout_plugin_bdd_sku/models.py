"""Data models for the BDD SKU plugin."""

from dataclasses import dataclass, field


@dataclass
class RetailPriceRow:
    """A cached retail price entry."""

    sku_name: str
    region: str
    currency: str
    price_hourly: float
    fetched_at_utc: str
    expires_at_utc: str
    is_fresh: bool = True

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON responses."""
        return {
            "sku_name": self.sku_name,
            "region": self.region,
            "currency": self.currency,
            "price_hourly": self.price_hourly,
            "fetched_at_utc": self.fetched_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "is_fresh": self.is_fresh,
        }


@dataclass
class SpotPricePoint:
    """A single spot price observation."""

    sku_name: str
    region: str
    os_type: str
    price_usd: float
    timestamp_utc: str
    ingested_at_utc: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON responses."""
        return {
            "sku_name": self.sku_name,
            "region": self.region,
            "os_type": self.os_type,
            "price_usd": self.price_usd,
            "timestamp_utc": self.timestamp_utc,
            "ingested_at_utc": self.ingested_at_utc,
        }


@dataclass
class SpotEvictionRate:
    """Latest eviction rate for a SKU+region."""

    sku_name: str
    region: str
    eviction_rate: str
    observed_at_utc: str

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON responses."""
        return {
            "sku_name": self.sku_name,
            "region": self.region,
            "eviction_rate": self.eviction_rate,
            "observed_at_utc": self.observed_at_utc,
        }


@dataclass
class WarmResult:
    """Result summary from a warm/ingest operation."""

    ok: bool
    dataset: str
    started_at: str
    finished_at: str | None = None
    regions_count: int = 0
    skus_count: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_fresh: int = 0
    no_price_count: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    run_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON responses."""
        return {
            "ok": self.ok,
            "dataset": self.dataset,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "regions_count": self.regions_count,
            "skus_count": self.skus_count,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped_fresh": self.skipped_fresh,
            "no_price_count": self.no_price_count,
            "errors": self.errors,
            "run_id": self.run_id,
        }


@dataclass
class CacheStatus:
    """Aggregate cache status."""

    retail_total: int = 0
    retail_fresh: int = 0
    retail_earliest_fetched: str | None = None
    retail_latest_fetched: str | None = None
    spot_history_total: int = 0
    spot_history_earliest_ts: str | None = None
    spot_history_latest_ts: str | None = None
    spot_history_latest_ingested: str | None = None
    eviction_total: int = 0
    eviction_latest_observed: str | None = None
    last_runs: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON responses."""
        return {
            "retail": {
                "total": self.retail_total,
                "fresh": self.retail_fresh,
                "earliest_fetched": self.retail_earliest_fetched,
                "latest_fetched": self.retail_latest_fetched,
            },
            "spot_history": {
                "total": self.spot_history_total,
                "earliest_ts": self.spot_history_earliest_ts,
                "latest_ts": self.spot_history_latest_ts,
                "latest_ingested": self.spot_history_latest_ingested,
            },
            "eviction": {
                "total": self.eviction_total,
                "latest_observed": self.eviction_latest_observed,
            },
            "last_runs": self.last_runs,
        }
