"""HTTP client for the standalone BDD-SKU API.

All functions are synchronous and use ``requests`` to call the external API.
The base URL is read from ``plugin_config.get_config().api_base_url``.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from az_scout_bdd_sku.plugin_config import get_config, is_configured

logger = logging.getLogger(__name__)

_TIMEOUT = 30


class ApiNotConfiguredError(Exception):
    """Raised when the API base URL has not been set."""


def _base_url() -> str:
    """Return the configured API base URL or raise."""
    if not is_configured():
        raise ApiNotConfiguredError("BDD-SKU API URL is not configured")
    return get_config().api_base_url.rstrip("/")


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Issue a GET request and return the parsed JSON response."""
    url = f"{_base_url()}{path}"
    if params:
        # Drop empty/None values
        params = {k: v for k, v in params.items() if v is not None and v != ""}
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------
# Legacy endpoints
# ------------------------------------------------------------------


def get_status() -> dict[str, Any]:
    """GET /status — cache status, row counts, last runs."""
    return _get("/status")  # type: ignore[no-any-return]


def get_spot_eviction_rates(
    region: str = "",
    sku_name: str = "",
    job_id: str = "",
) -> dict[str, Any]:
    """GET /spot/eviction-rates — spot eviction rates with optional filters."""
    return _get(  # type: ignore[no-any-return]
        "/spot/eviction-rates",
        {"region": region, "sku_name": sku_name, "job_id": job_id},
    )


def get_spot_price_history(
    region: str = "",
    sku_name: str = "",
    os_type: str = "",
) -> dict[str, Any]:
    """GET /spot/price-history — spot price history with optional filters."""
    return _get(  # type: ignore[no-any-return]
        "/spot/price-history",
        {"region": region, "sku_name": sku_name, "os_type": os_type},
    )


def get_spot_eviction_history() -> dict[str, Any]:
    """GET /spot/eviction-rates/history — available eviction rate snapshots."""
    return _get("/spot/eviction-rates/history")  # type: ignore[no-any-return]


# ------------------------------------------------------------------
# V1 endpoints
# ------------------------------------------------------------------


def v1_status() -> dict[str, Any]:
    """GET /v1/status — database status."""
    return _get("/v1/status")  # type: ignore[no-any-return]


def v1_list_locations(
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """GET /v1/locations — list distinct locations, paginated."""
    return _get("/v1/locations", {"limit": limit, "cursor": cursor})  # type: ignore[no-any-return]


def v1_list_skus(
    search: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """GET /v1/skus — list VM SKU names, paginated."""
    return _get(  # type: ignore[no-any-return]
        "/v1/skus",
        {"search": search, "limit": limit, "cursor": cursor},
    )


def v1_retail_prices(
    region: str = "",
    sku: str = "",
    currency: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """GET /v1/retail/prices — retail VM prices, paginated."""
    return _get(  # type: ignore[no-any-return]
        "/v1/retail/prices",
        {"region": region, "sku": sku, "currency": currency, "limit": limit, "cursor": cursor},
    )


def v1_eviction_rates(
    region: str = "",
    sku: str = "",
    limit: int = 1000,
    cursor: str = "",
) -> dict[str, Any]:
    """GET /v1/spot/eviction-rates — spot eviction rates, paginated."""
    return _get(  # type: ignore[no-any-return]
        "/v1/spot/eviction-rates",
        {"region": region, "sku": sku, "limit": limit, "cursor": cursor},
    )


def v1_eviction_rates_latest(
    region: str = "",
    sku: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    """GET /v1/spot/eviction-rates/latest — latest eviction rate per (region, sku)."""
    return _get(  # type: ignore[no-any-return]
        "/v1/spot/eviction-rates/latest",
        {"region": region, "sku": sku, "limit": limit},
    )


def test_connection(url: str) -> dict[str, Any]:
    """Test connectivity to *url* by hitting /health. Returns status dict."""
    try:
        resp = requests.get(f"{url.rstrip('/')}/health", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {"ok": True, "status": data.get("status", "unknown")}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}
