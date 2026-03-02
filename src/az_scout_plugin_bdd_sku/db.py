"""PostgreSQL connection pool and query helpers.

Uses psycopg3 (synchronous) with a ConnectionPool for efficiency.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

from az_scout_plugin_bdd_sku.config import get_config

logger = logging.getLogger(__name__)

_pool: ConnectionPool[psycopg.Connection[dict[str, Any]]] | None = None


def get_pool() -> ConnectionPool[psycopg.Connection[dict[str, Any]]]:
    """Return or create the global connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        cfg = get_config().database
        concurrency = get_config().cache.concurrency_limit
        logger.info(
            "Creating connection pool: host=%s port=%d db=%s min_size=1 max_size=%d",
            cfg.host,
            cfg.port,
            cfg.dbname,
            concurrency,
        )
        _pool = ConnectionPool(
            conninfo=cfg.dsn,
            min_size=1,
            max_size=concurrency,
            kwargs={"row_factory": dict_row},
        )
        logger.info("Connection pool created successfully")
    return _pool


@contextmanager
def get_conn() -> Generator[psycopg.Connection[dict[str, Any]], None, None]:
    """Yield a connection from the pool."""
    pool = get_pool()
    try:
        with pool.connection() as conn:
            yield conn
    except psycopg.OperationalError:
        logger.exception("Failed to get connection from pool")
        raise


def close_pool() -> None:
    """Close the connection pool if open."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Retail pricing queries
# ---------------------------------------------------------------------------


def upsert_retail_price(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str | None,
    currency: str,
    region: str,
    sku_name: str,
    price_hourly: float,
    ttl_hours: int,
    raw: dict[str, Any] | None = None,
) -> str:
    """Insert or update a retail price row. Returns 'inserted' or 'updated'."""
    now = datetime.now(UTC)
    expires = now + __import__("datetime").timedelta(hours=ttl_hours)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO retail_prices
                (tenant_id, currency, region, sku_name, price_hourly,
                 fetched_at_utc, expires_at_utc, raw)
            VALUES (%(tenant_id)s, %(currency)s, %(region)s, %(sku_name)s,
                    %(price_hourly)s, %(now)s, %(expires)s, %(raw)s)
            ON CONFLICT (currency, region, sku_name)
            DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                price_hourly = EXCLUDED.price_hourly,
                fetched_at_utc = EXCLUDED.fetched_at_utc,
                expires_at_utc = EXCLUDED.expires_at_utc,
                raw = EXCLUDED.raw
            RETURNING (xmax = 0) AS is_insert
            """,
            {
                "tenant_id": tenant_id,
                "currency": currency,
                "region": region,
                "sku_name": sku_name,
                "price_hourly": price_hourly,
                "now": now,
                "expires": expires,
                "raw": Json(raw) if raw else None,
            },
        )
        row = cur.fetchone()
        action = "inserted" if row and row["is_insert"] else "updated"
        logger.debug(
            "DB %s retail_prices: %s/%s/%s = %s",
            action,
            region,
            sku_name,
            currency,
            price_hourly,
        )
        return action


def is_retail_fresh(
    conn: psycopg.Connection[dict[str, Any]],
    currency: str,
    region: str,
    sku_name: str,
) -> bool:
    """Check if a retail price entry exists and is not expired."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM retail_prices
            WHERE currency = %s AND region = %s AND sku_name = %s
              AND expires_at_utc > now()
            """,
            (currency, region, sku_name),
        )
        return cur.fetchone() is not None


def get_retail_price(
    conn: psycopg.Connection[dict[str, Any]],
    region: str,
    sku_name: str,
    currency: str = "USD",
    tenant_id: str | None = None,
) -> dict[str, Any] | None:
    """Fetch a single cached retail price."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sku_name, region, currency, price_hourly,
                   fetched_at_utc, expires_at_utc,
                   (expires_at_utc > now()) AS is_fresh
            FROM retail_prices
            WHERE region = %s AND sku_name = %s AND currency = %s
            """,
            (region, sku_name, currency),
        )
        return cur.fetchone()


def query_retail_prices(
    conn: psycopg.Connection[dict[str, Any]],
    regions: list[str] | None = None,
    skus: list[str] | None = None,
    currency: str = "USD",
) -> list[dict[str, Any]]:
    """Query cached retail prices with optional filters."""
    clauses = ["currency = %(currency)s"]
    params: dict[str, Any] = {"currency": currency}

    if regions:
        clauses.append("region = ANY(%(regions)s)")
        params["regions"] = regions
    if skus:
        clauses.append("sku_name = ANY(%(skus)s)")
        params["skus"] = skus

    where = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT sku_name, region, currency, price_hourly,
                   fetched_at_utc, expires_at_utc,
                   (expires_at_utc > now()) AS is_fresh
            FROM retail_prices
            WHERE {where}
            ORDER BY region, sku_name
            """,  # noqa: S608
            params,
        )
        return list(cur.fetchall())


# ---------------------------------------------------------------------------
# Spot price history queries
# ---------------------------------------------------------------------------


def upsert_spot_price_points(
    conn: psycopg.Connection[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    """Bulk insert spot price points, skipping duplicates. Returns insert count."""
    if not rows:
        return 0
    logger.debug("DB upserting %d spot price points", len(rows))
    inserted = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO spot_price_points
                    (tenant_id, subscription_id, sku_name, region, os_type,
                     price_usd, timestamp_utc, ingested_at_utc, raw)
                VALUES (%(tenant_id)s, %(subscription_id)s, %(sku_name)s,
                        %(region)s, %(os_type)s, %(price_usd)s,
                        %(timestamp_utc)s, now(), %(raw)s)
                ON CONFLICT (sku_name, region, os_type, timestamp_utc)
                DO NOTHING
                """,
                {
                    "tenant_id": r.get("tenant_id"),
                    "subscription_id": r.get("subscription_id"),
                    "sku_name": r["sku_name"],
                    "region": r["region"],
                    "os_type": r["os_type"],
                    "price_usd": r["price_usd"],
                    "timestamp_utc": r["timestamp_utc"],
                    "raw": Json(r.get("raw")) if r.get("raw") else None,
                },
            )
            inserted += cur.rowcount
    logger.debug("DB inserted %d/%d spot price points", inserted, len(rows))
    return inserted


def query_spot_price_series(
    conn: psycopg.Connection[dict[str, Any]],
    sku_name: str,
    region: str,
    os_type: str = "linux",
    from_utc: str | None = None,
    to_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Return spot price time series for a specific SKU+region+OS."""
    clauses = [
        "sku_name = %(sku_name)s",
        "region = %(region)s",
        "os_type = %(os_type)s",
    ]
    params: dict[str, Any] = {
        "sku_name": sku_name,
        "region": region,
        "os_type": os_type,
    }
    if from_utc:
        clauses.append("timestamp_utc >= %(from_utc)s")
        params["from_utc"] = from_utc
    if to_utc:
        clauses.append("timestamp_utc <= %(to_utc)s")
        params["to_utc"] = to_utc

    where = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT sku_name, region, os_type, price_usd, timestamp_utc, ingested_at_utc
            FROM spot_price_points
            WHERE {where}
            ORDER BY timestamp_utc
            """,  # noqa: S608
            params,
        )
        return list(cur.fetchall())


# ---------------------------------------------------------------------------
# Spot eviction rate queries
# ---------------------------------------------------------------------------


def upsert_spot_eviction_rates(
    conn: psycopg.Connection[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    """Bulk insert/update eviction rates. Returns insert count."""
    if not rows:
        return 0
    logger.debug("DB upserting %d spot eviction rates", len(rows))
    inserted = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO spot_eviction_rates
                    (tenant_id, subscription_id, sku_name, region,
                     eviction_rate, observed_at_utc, raw)
                VALUES (%(tenant_id)s, %(subscription_id)s, %(sku_name)s,
                        %(region)s, %(eviction_rate)s, now(), %(raw)s)
                ON CONFLICT (sku_name, region, observed_at_utc)
                DO NOTHING
                """,
                {
                    "tenant_id": r.get("tenant_id"),
                    "subscription_id": r.get("subscription_id"),
                    "sku_name": r["sku_name"],
                    "region": r["region"],
                    "eviction_rate": r["eviction_rate"],
                    "raw": Json(r.get("raw")) if r.get("raw") else None,
                },
            )
            inserted += cur.rowcount
    logger.debug("DB inserted %d/%d spot eviction rates", inserted, len(rows))
    return inserted


def query_eviction_rates(
    conn: psycopg.Connection[dict[str, Any]],
    regions: list[str] | None = None,
    skus: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Query latest eviction rates per SKU+region."""
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if regions:
        clauses.append("region = ANY(%(regions)s)")
        params["regions"] = regions
    if skus:
        clauses.append("sku_name = ANY(%(skus)s)")
        params["skus"] = skus

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT ON (sku_name, region)
                   sku_name, region, eviction_rate, observed_at_utc
            FROM spot_eviction_rates
            {where}
            ORDER BY sku_name, region, observed_at_utc DESC
            """,  # noqa: S608
            params,
        )
        return list(cur.fetchall())


# ---------------------------------------------------------------------------
# Ingest run tracking
# ---------------------------------------------------------------------------


def create_ingest_run(
    conn: psycopg.Connection[dict[str, Any]],
    dataset: str,
) -> UUID:
    """Create a new ingest run record. Returns the run_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_runs (dataset, status)
            VALUES (%s, 'running')
            RETURNING run_id
            """,
            (dataset,),
        )
        row = cur.fetchone()
        assert row is not None  # noqa: S101
        run_id = UUID(str(row["run_id"]))
        logger.debug("DB created ingest_run %s for dataset=%s", run_id, dataset)
        return run_id


def finish_ingest_run(
    conn: psycopg.Connection[dict[str, Any]],
    run_id: UUID,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Mark an ingest run as finished."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET finished_at_utc = now(),
                status = %s,
                details = %s
            WHERE run_id = %s
            """,
            (
                status,
                Json(details) if details else None,
                str(run_id),
            ),
        )
    logger.debug("DB finished ingest_run %s status=%s", run_id, status)


def get_ingest_run(
    conn: psycopg.Connection[dict[str, Any]],
    run_id: UUID,
) -> dict[str, Any] | None:
    """Fetch a single ingest run by ID."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM ingest_runs WHERE run_id = %s",
            (str(run_id),),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Status / aggregates
# ---------------------------------------------------------------------------


def get_cache_status(
    conn: psycopg.Connection[dict[str, Any]],
) -> dict[str, Any]:
    """Return aggregate cache status for all datasets."""
    with conn.cursor() as cur:
        # Retail
        cur.execute(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE expires_at_utc > now()) AS fresh,
                   min(fetched_at_utc) AS earliest_fetched,
                   max(fetched_at_utc) AS latest_fetched
            FROM retail_prices
            """
        )
        retail = cur.fetchone() or {}

        # Spot history
        cur.execute(
            """
            SELECT count(*) AS total,
                   min(timestamp_utc) AS earliest_ts,
                   max(timestamp_utc) AS latest_ts,
                   max(ingested_at_utc) AS latest_ingested
            FROM spot_price_points
            """
        )
        spot_history = cur.fetchone() or {}

        # Eviction
        cur.execute(
            """
            SELECT count(*) AS total,
                   max(observed_at_utc) AS latest_observed
            FROM spot_eviction_rates
            """
        )
        eviction = cur.fetchone() or {}

        # Last runs
        cur.execute(
            """
            SELECT dataset, status, started_at_utc, finished_at_utc, details
            FROM ingest_runs
            WHERE (dataset, started_at_utc) IN (
                SELECT dataset, max(started_at_utc)
                FROM ingest_runs
                GROUP BY dataset
            )
            ORDER BY dataset
            """
        )
        last_runs = list(cur.fetchall())

    return {
        "retail": retail,
        "spot_history": spot_history,
        "eviction": eviction,
        "last_runs": last_runs,
    }


# ---------------------------------------------------------------------------
# Advisory lock helpers
# ---------------------------------------------------------------------------


def try_advisory_lock(
    conn: psycopg.Connection[dict[str, Any]],
    lock_key: int,
) -> bool:
    """Try to acquire a session-level advisory lock. Returns True if acquired."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
        row = cur.fetchone()
        return bool(row and row["pg_try_advisory_lock"])


def release_advisory_lock(
    conn: psycopg.Connection[dict[str, Any]],
    lock_key: int,
) -> None:
    """Release a session-level advisory lock."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
