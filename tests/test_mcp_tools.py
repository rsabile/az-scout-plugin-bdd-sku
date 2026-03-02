"""Tests for MCP tools (mocked DB)."""

import json
from unittest.mock import MagicMock, patch

from az_scout_plugin_bdd_sku.mcp_tools import (
    cache_status,
    retail_price_get,
    retail_prices_query,
    spot_eviction_rates_query,
    spot_price_series,
)


class TestCacheStatus:
    """Tests for cache_status MCP tool."""

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_cache_status")
    def test_returns_json_string(
        self,
        mock_status: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        mock_status.return_value = {
            "retail": {"total": 10, "fresh": 8, "latest_fetched": None},
            "spot_history": {"total": 50, "latest_ingested": None},
            "eviction": {"total": 5, "latest_observed": None},
            "last_runs": [],
        }
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = cache_status()
        data = json.loads(result)
        assert data["retail"]["total"] == 10
        assert data["retail"]["fresh"] == 8


class TestRetailPriceGet:
    """Tests for retail_price_get MCP tool."""

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_retail_price")
    def test_returns_price(
        self,
        mock_get: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        from decimal import Decimal

        mock_get.return_value = {
            "sku_name": "standard_d2s_v5",
            "region": "eastus",
            "currency": "USD",
            "price_hourly": Decimal("0.096"),
            "fetched_at_utc": "2026-01-01T00:00:00+00:00",
            "expires_at_utc": "2026-01-01T12:00:00+00:00",
            "is_fresh": True,
        }
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = retail_price_get("eastus", "standard_d2s_v5")
        data = json.loads(result)
        assert data["price_hourly"] == 0.096
        assert data["is_fresh"] is True

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_retail_price")
    def test_returns_null_when_not_found(
        self,
        mock_get: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        mock_get.return_value = None
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = retail_price_get("eastus", "nonexistent_sku")
        assert json.loads(result) is None


class TestRetailPricesQuery:
    """Tests for retail_prices_query MCP tool."""

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.query_retail_prices")
    def test_returns_list(
        self,
        mock_query: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        from decimal import Decimal

        mock_query.return_value = [
            {
                "sku_name": "standard_d2s_v5",
                "region": "eastus",
                "currency": "USD",
                "price_hourly": Decimal("0.096"),
                "fetched_at_utc": None,
                "expires_at_utc": None,
                "is_fresh": True,
            },
        ]
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = retail_prices_query(regions="eastus", skus="standard_d2s_v5")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["sku_name"] == "standard_d2s_v5"


class TestSpotEvictionRatesQuery:
    """Tests for spot_eviction_rates_query MCP tool."""

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.query_eviction_rates")
    def test_returns_rates(
        self,
        mock_query: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        mock_query.return_value = [
            {
                "sku_name": "standard_d2s_v5",
                "region": "eastus",
                "eviction_rate": "0-5%",
                "observed_at_utc": None,
            },
        ]
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = spot_eviction_rates_query(regions="eastus")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["eviction_rate"] == "0-5%"


class TestSpotPriceSeries:
    """Tests for spot_price_series MCP tool."""

    @patch("az_scout_plugin_bdd_sku.mcp_tools.get_conn")
    @patch("az_scout_plugin_bdd_sku.mcp_tools.query_spot_price_series")
    def test_returns_series(
        self,
        mock_query: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        from decimal import Decimal

        mock_query.return_value = [
            {
                "sku_name": "standard_d2s_v5",
                "region": "eastus",
                "os_type": "linux",
                "price_usd": Decimal("0.012"),
                "timestamp_utc": "2026-01-01T00:00:00+00:00",
            },
            {
                "sku_name": "standard_d2s_v5",
                "region": "eastus",
                "os_type": "linux",
                "price_usd": Decimal("0.013"),
                "timestamp_utc": "2026-01-02T00:00:00+00:00",
            },
        ]
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = spot_price_series("standard_d2s_v5", "eastus")
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["price_usd"] == 0.012
