"""Lightweight async DB helper for the plugin (query-only).

The plugin needs to read from Postgres for status / cached data queries
and proxy HTTP to the ingestion service for triggering runs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
import psycopg_pool

from az_scout_bdd_sku.plugin_config import get_config

_pool: psycopg_pool.AsyncConnectionPool | None = None


async def ensure_pool() -> psycopg_pool.AsyncConnectionPool:
    global _pool
    if _pool is None:
        cfg = get_config().database
        _pool = psycopg_pool.AsyncConnectionPool(
            conninfo=cfg.dsn,
            min_size=1,
            max_size=5,
            open=False,
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncIterator[psycopg.AsyncConnection[Any]]:
    pool = await ensure_pool()
    async with pool.connection() as conn:
        yield conn


async def is_healthy() -> bool:
    try:
        async with get_conn() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False
