"""Plugin configuration loader.

Reads from the TOML file pointed to by ``AZ_SCOUT_BDD_SKU_CONFIG`` or
from ``~/.config/az-scout/bdd-sku.toml``.  Returns typed dataclasses.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".config" / "az-scout" / "bdd-sku.toml"


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "azscout"
    user: str = "azscout"
    password: str = "azscout"
    sslmode: str = "disable"

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.dbname}"
            f"?sslmode={self.sslmode}"
        )


@dataclass
class PluginConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


_config: PluginConfig | None = None


def load_config() -> PluginConfig:
    """Load configuration from TOML file or return defaults."""
    path_str = os.environ.get("AZ_SCOUT_BDD_SKU_CONFIG", "")
    path = Path(path_str) if path_str else _DEFAULT_PATH

    if not path.is_file():
        logger.debug("Config file not found at %s – using defaults", path)
        return PluginConfig()

    import tomllib

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    db_raw = raw.get("database", {})

    db_cfg = DatabaseConfig(
        host=db_raw.get("host", "localhost"),
        port=int(db_raw.get("port", 5432)),
        dbname=db_raw.get("dbname", "azscout"),
        user=db_raw.get("user", "azscout"),
        password=db_raw.get("password", "azscout"),
        sslmode=db_raw.get("sslmode", "disable"),
    )

    logger.info("Loaded plugin config from %s", path)
    return PluginConfig(database=db_cfg)


def get_config() -> PluginConfig:
    """Return cached config, loading on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
