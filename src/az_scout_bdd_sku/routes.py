"""Plugin API routes for SKU DB Cache.

Mounted by az-scout under ``/plugins/bdd-sku/``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from az_scout_bdd_sku.db import get_conn, is_healthy

router = APIRouter()
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


@router.get("/status")
async def status() -> dict[str, Any]:
    """Cache status: database health, row count and last ingestion run."""
    db_ok = await is_healthy()

    count: int = -1
    last_run: dict[str, Any] | None = None

    if db_ok:
        try:
            async with get_conn() as conn:
                cur = await conn.execute("SELECT COUNT(*) FROM retail_prices_vm")
                row = await cur.fetchone()
                count = row[0] if row else 0
        except Exception:
            count = -1

        try:
            async with get_conn() as conn:
                cur = await conn.execute(
                    """
                    SELECT run_id, status, started_at_utc, finished_at_utc,
                           items_read, items_written, error_message
                    FROM job_runs WHERE dataset = 'azure_pricing'
                    ORDER BY started_at_utc DESC LIMIT 1
                    """
                )
                lr = await cur.fetchone()
                if lr:
                    last_run = {
                        "run_id": str(lr[0]),
                        "status": lr[1],
                        "started_at_utc": lr[2].isoformat() if lr[2] else None,
                        "finished_at_utc": lr[3].isoformat() if lr[3] else None,
                        "items_read": lr[4] or 0,
                        "items_written": lr[5] or 0,
                        "error_message": lr[6],
                    }
        except Exception:
            last_run = None

    return {
        "db_connected": db_ok,
        "retail_prices_count": count,
        "last_run": last_run,
    }
