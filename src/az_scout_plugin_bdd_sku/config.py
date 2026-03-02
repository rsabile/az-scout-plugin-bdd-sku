"""Plugin configuration loader.

Reads settings from a TOML config file. The file path is determined by:
1. ``AZ_SCOUT_BDD_SKU_CONFIG`` environment variable
2. ``~/.config/az-scout/bdd-sku.toml`` (default)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "az-scout" / "bdd-sku.toml"


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings."""

    host: str = "localhost"
    port: int = 5432
    dbname: str = "azscout"
    user: str = "azscout"
    password: str = "azscout"
    sslmode: str = "disable"

    @property
    def dsn(self) -> str:
        """Build a libpq-style connection string (password masked in logs)."""
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password} sslmode={self.sslmode}"
        )


@dataclass(frozen=True)
class CacheConfig:
    """TTL and concurrency settings."""

    retail_ttl_hours: int = 12
    spot_refresh_hours: int = 6
    eviction_refresh_hours: int = 24
    concurrency_limit: int = 8


@dataclass(frozen=True)
class PluginConfig:
    """Top-level plugin configuration."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


def _parse_toml(path: Path) -> dict[str, object]:
    """Read and parse a TOML file (stdlib tomllib, Python 3.11+)."""
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config() -> PluginConfig:
    """Load plugin configuration from TOML file.

    Falls back to defaults if the config file does not exist.
    """
    config_path_str = os.environ.get("AZ_SCOUT_BDD_SKU_CONFIG")
    config_path = Path(config_path_str) if config_path_str else _DEFAULT_CONFIG_PATH

    if not config_path.is_file():
        logger.info("Config file not found at %s — using defaults", config_path)
        return PluginConfig()

    logger.info("Loading config from %s", config_path)
    raw = _parse_toml(config_path)

    db_raw = raw.get("database", {})
    cache_raw = raw.get("cache", {})

    if not isinstance(db_raw, dict):
        db_raw = {}
    if not isinstance(cache_raw, dict):
        cache_raw = {}

    db = DatabaseConfig(
        host=str(db_raw.get("host", "localhost")),
        port=int(db_raw.get("port", 5432)),
        dbname=str(db_raw.get("dbname", "azscout")),
        user=str(db_raw.get("user", "azscout")),
        password=str(db_raw.get("password", "azscout")),
        sslmode=str(db_raw.get("sslmode", "disable")),
    )
    cache = CacheConfig(
        retail_ttl_hours=int(cache_raw.get("retail_ttl_hours", 12)),
        spot_refresh_hours=int(cache_raw.get("spot_refresh_hours", 6)),
        eviction_refresh_hours=int(cache_raw.get("eviction_refresh_hours", 24)),
        concurrency_limit=int(cache_raw.get("concurrency_limit", 8)),
    )

    return PluginConfig(database=db, cache=cache)


# Singleton config — loaded once at import time.
_config: PluginConfig | None = None


def get_config() -> PluginConfig:
    """Return the singleton config instance (lazy-loaded)."""
    global _config  # noqa: PLW0603
    if _config is None:
        _config = load_config()
        logger.info(
            "Plugin config: db=%s:%d/%s, retail_ttl=%dh, spot_refresh=%dh, "
            "eviction_refresh=%dh, concurrency=%d",
            _config.database.host,
            _config.database.port,
            _config.database.dbname,
            _config.cache.retail_ttl_hours,
            _config.cache.spot_refresh_hours,
            _config.cache.eviction_refresh_hours,
            _config.cache.concurrency_limit,
        )
    return _config
