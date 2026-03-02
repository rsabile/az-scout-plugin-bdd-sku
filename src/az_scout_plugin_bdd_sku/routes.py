"""FastAPI routes for the BDD SKU plugin.

Mounted at ``/plugins/bdd-sku/`` by the core plugin system.
"""

import logging
from typing import Any

from fastapi import APIRouter

from az_scout_plugin_bdd_sku.db import get_cache_status, get_conn, get_ingest_run
from az_scout_plugin_bdd_sku.models import CacheStatus

logger = logging.getLogger(__name__)
router = APIRouter()

_logging_configured = False


def _ensure_logging() -> None:
    """Copy az_scout logger's handlers/level to the plugin logger tree.

    Called lazily on first route invocation so that the CLI's
    ``_setup_logging(level=DEBUG)`` has already run.

    If the core logger is at WARNING or higher (the default when ``-v``
    is not passed), the plugin logger is forced to INFO so that
    diagnostic messages are always visible.
    """
    global _logging_configured  # noqa: PLW0603
    if _logging_configured:
        return
    _logging_configured = True
    source = logging.getLogger("az_scout")
    target = logging.getLogger("az_scout_plugin_bdd_sku")

    # Copy handlers from core logger
    if source.handlers and not target.handlers:
        for h in source.handlers:
            target.addHandler(h)

    # If no handlers ended up on the target (e.g. core not configured yet),
    # add a basic StreamHandler so logs are never silently lost.
    if not target.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s - %(message)s"))
        target.addHandler(handler)

    # Use the core level, but floor at INFO for plugin diagnostics.
    effective = min(source.level or logging.WARNING, logging.INFO)
    target.setLevel(effective)
    target.propagate = False

    logger.info(
        "Plugin logging configured: level=%s, handlers=%d (core level=%s)",
        logging.getLevelName(target.level),
        len(target.handlers),
        logging.getLevelName(source.level),
    )


def _serialize_status(raw: dict[str, Any]) -> dict[str, object]:
    """Convert raw DB status to a CacheStatus model."""
    retail = raw.get("retail", {})
    spot = raw.get("spot_history", {})
    eviction = raw.get("eviction", {})
    runs = raw.get("last_runs", [])

    def _iso(v: Any) -> str | None:
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    status = CacheStatus(
        retail_total=int(retail.get("total", 0) or 0),
        retail_fresh=int(retail.get("fresh", 0) or 0),
        retail_earliest_fetched=_iso(retail.get("earliest_fetched")),
        retail_latest_fetched=_iso(retail.get("latest_fetched")),
        spot_history_total=int(spot.get("total", 0) or 0),
        spot_history_earliest_ts=_iso(spot.get("earliest_ts")),
        spot_history_latest_ts=_iso(spot.get("latest_ts")),
        spot_history_latest_ingested=_iso(spot.get("latest_ingested")),
        eviction_total=int(eviction.get("total", 0) or 0),
        eviction_latest_observed=_iso(eviction.get("latest_observed")),
        last_runs=[
            {
                "dataset": r.get("dataset", ""),
                "status": r.get("status", ""),
                "started_at_utc": _iso(r.get("started_at_utc")),
                "finished_at_utc": _iso(r.get("finished_at_utc")),
            }
            for r in runs
        ],
    )
    return status.to_dict()


@router.get("/status")
async def cache_status() -> dict[str, object]:
    """Return aggregate cache status for all datasets."""
    _ensure_logging()
    with get_conn() as conn:
        raw = get_cache_status(conn)
    return _serialize_status(raw)


@router.post("/warm/retail")
def warm_retail(
    body: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Warm the retail pricing cache.

    Body (all optional):
    - currency: str (default "USD")
    - sku_sample: list[str] (default: curated VM list)
    - ttl_hours: int (default: from config)
    - force: bool (default: false — skip fresh entries)
    - tenant_id: str | None
    """
    from az_scout_plugin_bdd_sku.service.retail_pricing import warm_retail_pricing

    _ensure_logging()
    params = body or {}
    logger.info(
        "Warm retail: currency=%s, force=%s",
        params.get("currency", "USD"),
        params.get("force", False),
    )
    result = warm_retail_pricing(
        currency=str(params.get("currency", "USD")),
        sku_sample=params.get("sku_sample"),
        ttl_hours=params.get("ttl_hours"),
        force=bool(params.get("force", False)),
        tenant_id=params.get("tenant_id"),
    )
    logger.info(
        "Warm retail done: %d inserted, %d updated, %d errors",
        result.inserted,
        result.updated,
        len(result.errors),
    )
    return result.to_dict()


@router.post("/warm/spot")
def warm_spot(
    body: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Warm the spot cache (history + eviction rates).

    Body (all optional):
    - subscriptions: list[str] (default: auto-discover)
    - locations: list[str] (default: all regions from core)
    - sku_sample: list[str] (default: curated VM list)
    - os_type: str (default: "linux")
    - force: bool (default: false)
    - tenant_id: str | None
    """
    from az_scout_plugin_bdd_sku.service.spot_data import warm_spot_data

    _ensure_logging()
    params = body or {}
    logger.info(
        "Warm spot: os_type=%s, force=%s",
        params.get("os_type", "linux"),
        params.get("force", False),
    )
    result = warm_spot_data(
        subscriptions=params.get("subscriptions"),
        locations=params.get("locations"),
        sku_sample=params.get("sku_sample"),
        os_type=str(params.get("os_type", "linux")),
        force=bool(params.get("force", False)),
        tenant_id=params.get("tenant_id"),
    )
    logger.info("Warm spot done: %d inserted, %d errors", result.inserted, len(result.errors))
    return result.to_dict()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, object]:
    """Get details of a specific ingest run."""
    from uuid import UUID

    try:
        uid = UUID(run_id)
    except ValueError:
        return {"error": "Invalid run_id format"}

    with get_conn() as conn:
        row = get_ingest_run(conn, uid)

    if row is None:
        return {"error": "Run not found"}

    def _iso(v: Any) -> str | None:
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    return {
        "run_id": str(row["run_id"]),
        "dataset": row["dataset"],
        "status": row["status"],
        "started_at_utc": _iso(row.get("started_at_utc")),
        "finished_at_utc": _iso(row.get("finished_at_utc")),
        "details": row.get("details"),
    }
