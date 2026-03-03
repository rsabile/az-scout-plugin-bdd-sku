"""MCP tools for the SKU DB Cache plugin.

All tools call the standalone BDD-SKU API via ``api_client``.
The API base URL must be configured in the plugin settings.
"""

from __future__ import annotations

from typing import Any

from az_scout_bdd_sku.api_client import ApiNotConfiguredError
from az_scout_bdd_sku.api_client import get_spot_eviction_history as _api_eviction_history
from az_scout_bdd_sku.api_client import get_spot_eviction_rates as _api_eviction_rates
from az_scout_bdd_sku.api_client import get_spot_price_history as _api_price_history
from az_scout_bdd_sku.api_client import get_status as _api_status
from az_scout_bdd_sku.api_client import v1_eviction_rates as _api_v1_eviction_rates
from az_scout_bdd_sku.api_client import v1_eviction_rates_latest as _api_v1_eviction_rates_latest
from az_scout_bdd_sku.api_client import v1_list_locations as _api_v1_list_locations
from az_scout_bdd_sku.api_client import v1_list_skus as _api_v1_list_skus
from az_scout_bdd_sku.api_client import v1_retail_prices as _api_v1_retail_prices
from az_scout_bdd_sku.api_client import v1_status as _api_v1_status

_NOT_CONFIGURED = {"error": "BDD-SKU API URL is not configured. Set it in the plugin settings."}


def _safe_call(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call *fn* and catch ApiNotConfiguredError + request errors."""
    try:
        return fn(*args, **kwargs)  # type: ignore[no-any-return]
    except ApiNotConfiguredError:
        return _NOT_CONFIGURED
    except Exception as exc:
        return {"error": f"API call failed: {exc}"}


def cache_status() -> dict[str, Any]:
    """Return the current cache status: DB health, row counts, regions, SKUs, and last runs."""
    return _safe_call(_api_status)


def get_spot_eviction_rates(
    region: str = "",
    sku_name: str = "",
    job_id: str = "",
) -> dict[str, Any]:
    """Query cached spot eviction rates.

    Optionally filter by region, sku_name (substring), or job_id.
    Without job_id returns the latest snapshot only.
    """
    return _safe_call(_api_eviction_rates, region, sku_name, job_id)


def get_spot_price_history(
    region: str = "",
    sku_name: str = "",
    os_type: str = "",
) -> dict[str, Any]:
    """Query cached spot price history.

    Optionally filter by region, sku_name (substring), or os_type.
    """
    return _safe_call(_api_price_history, region, sku_name, os_type)


def get_spot_eviction_history() -> dict[str, Any]:
    """List available eviction rate snapshots (job_id, job_datetime, row_count)."""
    return _safe_call(_api_eviction_history)


# ==================================================================
# V1 MCP tools
# ==================================================================


def v1_status() -> dict[str, Any]:
    """Return v1 database status: health, row counts, last job per dataset."""
    return _safe_call(_api_v1_status)


def v1_list_locations(
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """List distinct Azure location names across all tables. Paginated (keyset cursor)."""
    return _safe_call(_api_v1_list_locations, limit, cursor)


def v1_list_skus(
    search: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """List distinct VM SKU names. Optional substring search. Paginated."""
    return _safe_call(_api_v1_list_skus, search, limit, cursor)


def v1_retail_prices(
    region: str = "",
    sku: str = "",
    currency: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """Query retail VM prices with filters. Paginated (keyset cursor)."""
    return _safe_call(_api_v1_retail_prices, region, sku, currency, limit, cursor)


def v1_eviction_rates(
    region: str = "",
    sku: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """Query spot eviction rates with filters. Paginated (keyset cursor)."""
    return _safe_call(_api_v1_eviction_rates, region, sku, limit, cursor)


def v1_eviction_rates_latest(
    region: str = "",
    sku: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    """Latest eviction rate per (region, sku_name). Not paginated."""
    return _safe_call(_api_v1_eviction_rates_latest, region, sku, limit)
