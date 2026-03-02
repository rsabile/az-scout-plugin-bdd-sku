"""Tests for plugin configuration loader."""

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

from az_scout_plugin_bdd_sku.config import (
    CacheConfig,
    DatabaseConfig,
    PluginConfig,
    load_config,
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_defaults(self) -> None:
        cfg = DatabaseConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.dbname == "azscout"
        assert cfg.sslmode == "disable"

    def test_dsn(self) -> None:
        cfg = DatabaseConfig(host="db.example.com", port=5433, dbname="test")
        dsn = cfg.dsn
        assert "host=db.example.com" in dsn
        assert "port=5433" in dsn
        assert "dbname=test" in dsn


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_defaults(self) -> None:
        cfg = CacheConfig()
        assert cfg.retail_ttl_hours == 12
        assert cfg.spot_refresh_hours == 6
        assert cfg.eviction_refresh_hours == 24
        assert cfg.concurrency_limit == 8


class TestLoadConfig:
    """Tests for load_config function."""

    def test_defaults_when_no_file(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"AZ_SCOUT_BDD_SKU_CONFIG": str(tmp_path / "nope.toml")}):
            cfg = load_config()
        assert isinstance(cfg, PluginConfig)
        assert cfg.database.host == "localhost"
        assert cfg.cache.retail_ttl_hours == 12

    def test_loads_from_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "test.toml"
        config_file.write_text(
            textwrap.dedent("""\
            [database]
            host = "pg.local"
            port = 5433
            dbname = "testdb"
            user = "testuser"
            password = "secret"
            sslmode = "require"

            [cache]
            retail_ttl_hours = 6
            concurrency_limit = 4
        """)
        )

        with patch.dict(os.environ, {"AZ_SCOUT_BDD_SKU_CONFIG": str(config_file)}):
            cfg = load_config()

        assert cfg.database.host == "pg.local"
        assert cfg.database.port == 5433
        assert cfg.database.dbname == "testdb"
        assert cfg.database.sslmode == "require"
        assert cfg.cache.retail_ttl_hours == 6
        assert cfg.cache.concurrency_limit == 4
        # Unset values use defaults
        assert cfg.cache.spot_refresh_hours == 6
