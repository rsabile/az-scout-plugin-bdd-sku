-- BDD SKU plugin schema for az-scout
-- Stores cached VM retail pricing, Spot price history, and Spot eviction rates.

-- Retail VM pricing cache (from core /api/sku-pricing)
CREATE TABLE IF NOT EXISTS retail_prices (
    tenant_id       TEXT,
    currency        TEXT        NOT NULL,
    region          TEXT        NOT NULL,
    sku_name        TEXT        NOT NULL,
    price_hourly    NUMERIC     NOT NULL,
    fetched_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at_utc  TIMESTAMPTZ NOT NULL,
    raw             JSONB,
    PRIMARY KEY (currency, region, sku_name)
);

CREATE INDEX IF NOT EXISTS idx_retail_prices_expires
    ON retail_prices (expires_at_utc);

-- Spot price history points (from ARG SpotResources)
CREATE TABLE IF NOT EXISTS spot_price_points (
    tenant_id       TEXT,
    subscription_id TEXT,
    sku_name        TEXT        NOT NULL,
    region          TEXT        NOT NULL,
    os_type         TEXT        NOT NULL,
    price_usd       NUMERIC     NOT NULL,
    timestamp_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw             JSONB,
    UNIQUE (sku_name, region, os_type, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_spot_price_region
    ON spot_price_points (region);
CREATE INDEX IF NOT EXISTS idx_spot_price_sku
    ON spot_price_points (sku_name);
CREATE INDEX IF NOT EXISTS idx_spot_price_ts
    ON spot_price_points (timestamp_utc);

-- Spot eviction rates (from ARG SpotResources)
CREATE TABLE IF NOT EXISTS spot_eviction_rates (
    tenant_id       TEXT,
    subscription_id TEXT,
    sku_name        TEXT        NOT NULL,
    region          TEXT        NOT NULL,
    eviction_rate   TEXT        NOT NULL,
    observed_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw             JSONB,
    UNIQUE (sku_name, region, observed_at_utc)
);

CREATE INDEX IF NOT EXISTS idx_spot_eviction_region
    ON spot_eviction_rates (region);
CREATE INDEX IF NOT EXISTS idx_spot_eviction_sku
    ON spot_eviction_rates (sku_name);
CREATE INDEX IF NOT EXISTS idx_spot_eviction_ts
    ON spot_eviction_rates (observed_at_utc);

-- Ingest run tracking
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset         TEXT        NOT NULL,
    started_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at_utc TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',
    details         JSONB
);
