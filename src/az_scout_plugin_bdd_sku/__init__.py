"""az-scout plugin: BDD SKU.

PostgreSQL-backed cache for VM retail pricing, Spot price history,
and Spot eviction rates. Provides a UI tab for cache warming and
MCP tools for querying cached data.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from az_scout.plugin_api import TabDefinition
from fastapi import APIRouter

_STATIC_DIR = Path(__file__).parent / "static"

__version__ = "0.1.0"


class BddSkuPlugin:
    """BDD SKU az-scout plugin."""

    name = "bdd-sku"
    version = __version__

    def get_router(self) -> APIRouter | None:
        """Return API routes mounted at /plugins/bdd-sku/."""
        from az_scout_plugin_bdd_sku.routes import router

        return router

    def get_mcp_tools(self) -> list[Callable[..., Any]] | None:
        """Return MCP tool functions."""
        from az_scout_plugin_bdd_sku.mcp_tools import (
            cache_status,
            retail_price_get,
            retail_prices_query,
            spot_eviction_rates_query,
            spot_price_series,
        )

        return [
            cache_status,
            retail_price_get,
            retail_prices_query,
            spot_eviction_rates_query,
            spot_price_series,
        ]

    def get_static_dir(self) -> Path | None:
        """Return path to static assets directory."""
        return _STATIC_DIR

    def get_tabs(self) -> list[TabDefinition] | None:
        """Return UI tab definitions."""
        return [
            TabDefinition(
                id="bdd-sku",
                label="SKU DB Cache",
                icon="bi bi-database",
                js_entry="js/bdd-sku.js",
                css_entry="css/bdd-sku.css",
            )
        ]

    def get_chat_modes(self) -> list[Any] | None:
        """No chat modes for this plugin."""
        return None


# Module-level instance — referenced by the entry point
plugin = BddSkuPlugin()
