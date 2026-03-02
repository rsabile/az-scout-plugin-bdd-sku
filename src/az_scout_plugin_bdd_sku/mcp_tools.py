"""MCP tools for the BDD SKU plugin.

These tools expose cached VM pricing, spot price history, and eviction
rates from the PostgreSQL database to LLM flows and other plugins.

Data sources:
- Retail pricing: cached from core ``/api/sku-pricing`` (Azure Retail Prices API)
- Spot price history: cached from Azure Resource Graph ``SpotResources``
- Eviction rates: cached from Azure Resource Graph ``SpotResources``

All data is a curated sample of commonly-used VM SKUs and may not cover
every SKU/region combination. Check ``cache_status()`` for freshness.
"""

import json
from typing import Any

from az_scout_plugin_bdd_sku.db import (
    get_cache_status,
    get_conn,
    get_retail_price,
    query_eviction_rates,
    query_retail_prices,
    query_spot_price_series,
)


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def cache_status(tenant_id: str | None = None) -> str:
    """Return record counts and last ingest run timestamps for all cached datasets.

    Datasets: retail (VM hourly prices), spot_history (spot price points),
    spot_eviction (eviction rate observations).

    No Azure credentials required — reads from local PostgreSQL cache.
    """
    with get_conn() as conn:
        raw = get_cache_status(conn)

    retail = raw.get("retail", {})
    spot = raw.get("spot_history", {})
    eviction = raw.get("eviction", {})
    runs = raw.get("last_runs", [])

    result = {
        "retail": {
            "total": int(retail.get("total", 0) or 0),
            "fresh": int(retail.get("fresh", 0) or 0),
            "latest_fetched": _iso(retail.get("latest_fetched")),
        },
        "spot_history": {
            "total": int(spot.get("total", 0) or 0),
            "latest_ingested": _iso(spot.get("latest_ingested")),
        },
        "eviction": {
            "total": int(eviction.get("total", 0) or 0),
            "latest_observed": _iso(eviction.get("latest_observed")),
        },
        "last_runs": [
            {
                "dataset": r.get("dataset", ""),
                "status": r.get("status", ""),
                "started_at_utc": _iso(r.get("started_at_utc")),
            }
            for r in runs
        ],
    }
    return json.dumps(result, default=str)


def retail_price_get(
    region: str,
    sku_name: str,
    currency: str = "USD",
    tenant_id: str | None = None,
) -> str:
    """Return a single cached retail VM price for a specific region and SKU.

    Data source: Azure Retail Prices API (cached via core /api/sku-pricing).
    Freshness is based on the TTL set during cache warming (typically 12h).
    Returns null if the SKU/region is not in the cache.

    Parameters:
        region: Azure region name (e.g. 'eastus', 'westeurope')
        sku_name: VM SKU name in lowercase (e.g. 'standard_d2s_v5')
        currency: ISO 4217 currency code (default 'USD')
    """
    with get_conn() as conn:
        row = get_retail_price(conn, region, sku_name, currency, tenant_id)

    if row is None:
        return json.dumps(None)

    return json.dumps(
        {
            "sku_name": row["sku_name"],
            "region": row["region"],
            "currency": row["currency"],
            "price_hourly": float(row["price_hourly"]),
            "fetched_at_utc": _iso(row.get("fetched_at_utc")),
            "expires_at_utc": _iso(row.get("expires_at_utc")),
            "is_fresh": row.get("is_fresh", False),
        },
        default=str,
    )


def retail_prices_query(
    regions: str | None = None,
    skus: str | None = None,
    currency: str = "USD",
    tenant_id: str | None = None,
) -> str:
    """Query cached retail VM prices with filters. Returns a list.

    Data source: Azure Retail Prices API (cached via core /api/sku-pricing).
    Only covers a curated sample of VM SKUs.

    Parameters:
        regions: comma-separated region names (e.g. 'eastus,westeurope') or null for all
        skus: comma-separated SKU names (e.g. 'standard_d2s_v5,standard_f4s_v2') or null for all
        currency: ISO 4217 currency code (default 'USD')
    """
    region_list = [r.strip() for r in regions.split(",")] if regions else None
    sku_list = [s.strip() for s in skus.split(",")] if skus else None

    with get_conn() as conn:
        rows = query_retail_prices(conn, region_list, sku_list, currency)

    return json.dumps(
        [
            {
                "sku_name": r["sku_name"],
                "region": r["region"],
                "currency": r["currency"],
                "price_hourly": float(r["price_hourly"]),
                "fetched_at_utc": _iso(r.get("fetched_at_utc")),
                "expires_at_utc": _iso(r.get("expires_at_utc")),
                "is_fresh": r.get("is_fresh", False),
            }
            for r in rows
        ],
        default=str,
    )


def spot_eviction_rates_query(
    regions: str | None = None,
    skus: str | None = None,
    tenant_id: str | None = None,
) -> str:
    """Query latest cached spot eviction rates per SKU and region.

    Data source: Azure Resource Graph SpotResources
    (type microsoft.compute/skuspotevictionrate/location).
    Eviction rate is a string like '0-5%', '5-10%', etc.

    Parameters:
        regions: comma-separated region names or null for all
        skus: comma-separated SKU names or null for all
    """
    region_list = [r.strip() for r in regions.split(",")] if regions else None
    sku_list = [s.strip() for s in skus.split(",")] if skus else None

    with get_conn() as conn:
        rows = query_eviction_rates(conn, region_list, sku_list)

    return json.dumps(
        [
            {
                "sku_name": r["sku_name"],
                "region": r["region"],
                "eviction_rate": r["eviction_rate"],
                "observed_at_utc": _iso(r.get("observed_at_utc")),
            }
            for r in rows
        ],
        default=str,
    )


def spot_price_series(
    sku_name: str,
    region: str,
    os_type: str = "linux",
    from_utc: str | None = None,
    to_utc: str | None = None,
    tenant_id: str | None = None,
) -> str:
    """Return a time series of cached spot prices for a specific SKU+region.

    Data source: Azure Resource Graph SpotResources
    (type microsoft.compute/skuspotpricehistory/ostype/location).
    Only covers a curated sample of VM SKUs.

    Parameters:
        sku_name: VM SKU name in lowercase (e.g. 'standard_d2s_v5')
        region: Azure region name (e.g. 'eastus')
        os_type: OS type (default 'linux')
        from_utc: start of time range (ISO 8601) or null for all
        to_utc: end of time range (ISO 8601) or null for all
    """
    with get_conn() as conn:
        rows = query_spot_price_series(conn, sku_name, region, os_type, from_utc, to_utc)

    return json.dumps(
        [
            {
                "sku_name": r["sku_name"],
                "region": r["region"],
                "os_type": r["os_type"],
                "price_usd": float(r["price_usd"]),
                "timestamp_utc": _iso(r.get("timestamp_utc")),
            }
            for r in rows
        ],
        default=str,
    )
