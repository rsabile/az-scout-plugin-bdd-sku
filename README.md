# az-scout-plugin-bdd-sku

[![CI](https://github.com/rsabile/az-scout-plugin-bdd-sku/actions/workflows/ci.yml/badge.svg)](https://github.com/rsabile/az-scout-plugin-bdd-sku/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/az-scout-bdd-sku)](https://pypi.org/project/az-scout-bdd-sku/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**SKU DB Cache** plugin for [az-scout](https://github.com/lrivallain/az-scout) — adds a UI tab and 24 MCP tools for querying Azure VM pricing, spot eviction rates, and availability data. This plugin is a **lightweight HTTP client** that proxies all requests to the standalone [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api).

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    az-scout (core)                    │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │          az-scout-plugin-bdd-sku                │ │
│  │                                                 │ │
│  │  Plugin Routes     MCP Tools      UI Tab        │ │
│  │  /status           24 tools       SKU DB Cache  │ │
│  │  /settings         (LLM chat)     (D3 charts)   │ │
│  └────────┬────────────────────────────────────────┘ │
│           │ HTTP                                     │
└───────────┼──────────────────────────────────────────┘
            │
            ▼
┌───────────────────────┐       ┌──────────────────────────┐
│  az-scout-bdd-api     │       │  az-scout-bdd-ingestion   │
│  (REST API)           │◄──────│  (data pipeline)          │
│  Container App        │  PG   │  Ingestion + SKU Mapper   │
│  25 endpoints         │       │  + Price Aggregator       │
└───────────┬───────────┘       └────────────┬─────────────┘
            │                                │
            ▼                                ▼
       ┌──────────────────────────────────────────┐
       │           PostgreSQL 17                   │
       │           (Azure Flexible Server)         │
       └──────────────────────────────────────────┘
```

The plugin itself contains **no database code** — it calls the API over HTTP via `api_client.py`.

## Prerequisites

- [az-scout](https://github.com/lrivallain/az-scout) ≥ 2026.1
- Python 3.11+
- A running instance of [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api) with ingested data from [az-scout-bdd-ingestion](https://github.com/rsabile/az-scout-bdd-ingestion)

## Installation

```bash
# Install the plugin (automatically discovered by az-scout)
pip install az-scout-bdd-sku

# Or install in development mode
pip install -e .
```

## Configuration

The plugin needs to know the URL of the standalone API. Configure it via any of these methods (in priority order):

### 1. Environment variable

```bash
export BDD_SKU_API_URL="https://my-api.azurecontainerapps.io"
```

### 2. TOML config file

```toml
# ~/.config/az-scout/bdd-sku.toml
[api]
base_url = "https://my-api.azurecontainerapps.io"
```

Override the config file path with `AZ_SCOUT_BDD_SKU_CONFIG=/path/to/config.toml`.

### 3. Settings UI

The plugin adds a **Settings** button in the tab header. Configure the API URL directly from the az-scout web interface — the value is persisted to the TOML config file.

## MCP Tools

The plugin exposes 24 tools on the az-scout MCP server, usable by LLMs in the integrated chat. All tools proxy to the standalone API.

| Tool | Parameters | Description |
|---|---|---|
| `cache_status` | *(none)* | Database status: connectivity, count per table, last run |
| `get_spot_eviction_rates` | `region?`, `sku_name?`, `job_id?` | Spot eviction rates. Without `job_id` → latest snapshot |
| `get_spot_eviction_history` | *(none)* | Lists available eviction snapshots (last 50) |
| `get_spot_price_history` | `region?`, `sku_name?`, `os_type?` | Spot price history per SKU×region×OS |
| `v1_status` | *(none)* | v1 status: DB health, stats per dataset |
| `v1_list_locations` | `limit?`, `cursor?` | List Azure regions (paginated) |
| `v1_list_skus` | `search?`, `limit?`, `cursor?` | List VM SKUs (paginated) |
| `v1_retail_prices` | `region?`, `sku?`, `currency?`, `snapshot_date?`, `limit?`, `cursor?` | VM retail prices (paginated) |
| `v1_eviction_rates` | `region?`, `sku?`, `snapshot_date?`, `limit?`, `cursor?` | Spot eviction rates (paginated) |
| `v1_eviction_rates_latest` | `region?`, `sku?`, `snapshot_date?`, `limit?` | Latest eviction rate per (region, sku) |
| `v1_pricing_categories` | `limit?`, `cursor?` | Distinct pricing categories (paginated) |
| `v1_pricing_summary` | `region?`, `category?`, `priceType?`, `snapshotSince?`, `limit?`, `cursor?` | Aggregated price summaries (multi-value, paginated) |
| `v1_pricing_summary_latest` | `region?`, `category?`, `priceType?`, `limit?`, `cursor?` | Summaries from latest run (paginated) |
| `v1_pricing_summary_series` | `region`, `priceType`, `bucket`, `metric?`, `category?` | Time series of a price metric |
| `v1_pricing_cheapest` | `priceType`, `metric?`, `category?`, `limit?` | Top N cheapest regions |
| `v1_sku_catalog` | `search?`, `category?`, `family?`, `min_vcpus?`, `max_vcpus?`, `limit?`, `cursor?` | Full VM SKU catalog (paginated) |
| `v1_jobs` | `dataset?`, `status?`, `limit?`, `cursor?` | Ingestion job runs (paginated, most recent first) |
| `v1_job_logs` | `run_id`, `level?`, `limit?`, `cursor?` | Logs for a specific job run (paginated) |
| `v1_spot_prices_series` | `region`, `sku`, `os_type?`, `bucket?` | Spot price time series (denormalized JSONB) |
| `v1_retail_prices_compare` | `sku`, `currency?`, `pricing_type?`, `snapshot_date?` | Compare a SKU across all regions |
| `v1_spot_detail` | `region`, `sku`, `os_type?`, `snapshot_date?` | Composite Spot detail (price + eviction + catalog) |
| `v1_savings_plans` | `region?`, `sku?`, `currency?`, `snapshot_date?`, `limit?`, `cursor?` | Retail prices with savings plan data (paginated) |
| `v1_pricing_summary_compare` | `regions`, `price_type?`, `category?` | Compare pricing summaries between regions |
| `v1_stats` | *(none)* | Global dashboard metrics |

## API Reference

The plugin proxies to the standalone [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api) which exposes 29 read-only endpoints (4 legacy + 25 v1). Interactive docs are available at `/docs` (Swagger UI) and `/redoc` on your API instance.

OpenAPI spec: [`openapi/v1.yaml`](openapi/v1.yaml) (reference copy)

### Legacy endpoints

| Path | Parameters | Description |
|---|---|---|
| `GET /status` | — | DB health, row counts, regions, SKUs, last runs |
| `GET /spot/eviction-rates` | `region?`, `sku_name?`, `job_id?`, `limit?` | Spot eviction rates (latest snapshot by default) |
| `GET /spot/eviction-rates/history` | `limit?` | Available eviction rate snapshots |
| `GET /spot/price-history` | `region?`, `sku_name?`, `os_type?`, `limit?` | Spot price history |

### V1 endpoints — Reference data

| Path | Parameters | Description |
|---|---|---|
| `GET /v1/status` | — | Database health and per-dataset statistics |
| `GET /v1/locations` | `limit?`, `cursor?` | Distinct locations across all tables |
| `GET /v1/skus` | `search?`, `limit?`, `cursor?` | Distinct SKU names |
| `GET /v1/currencies` | `limit?`, `cursor?` | Distinct currency codes |
| `GET /v1/os-types` | `limit?`, `cursor?` | Distinct OS types |
| `GET /v1/stats` | — | Global dashboard metrics (counts, freshness) |

### V1 endpoints — Retail pricing

| Path | Parameters | Description |
|---|---|---|
| `GET /v1/retail/prices` | `region?`, `sku?`, `currency?`, `effectiveAt?`, `updatedSince?`, `snapshotDate?`, `limit?`, `cursor?` | Retail VM prices with filters |
| `GET /v1/retail/prices/latest` | `region?`, `sku?`, `currency?`, `snapshotDate?`, `limit?`, `cursor?` | Latest retail price per unique key |
| `GET /v1/retail/prices/compare` | `sku` *(required)*, `currency?`, `pricingType?`, `snapshotDate?` | Compare SKU retail price across all regions |
| `GET /v1/retail/savings-plans` | `region?`, `sku?`, `currency?`, `snapshotDate?`, `limit?`, `cursor?` | Retail prices with savings plan data |

### V1 endpoints — Spot pricing

| Path | Parameters | Description |
|---|---|---|
| `GET /v1/spot/prices` | `region?`, `sku?`, `osType?`, `sample?`, `limit?`, `cursor?` | Spot price history (raw sampling) |
| `GET /v1/spot/prices/series` | `region` *(req)*, `sku` *(req)*, `osType?`, `bucket?` | Spot price time series |
| `GET /v1/spot/eviction-rates` | `region?`, `sku?`, `updatedSince?`, `snapshotDate?`, `limit?`, `cursor?` | Spot eviction rates |
| `GET /v1/spot/eviction-rates/series` | `region` *(req)*, `sku` *(req)*, `bucket` *(req)*, `agg?` | Time-bucketed eviction rate aggregation |
| `GET /v1/spot/eviction-rates/latest` | `region?`, `sku?`, `snapshotDate?`, `limit?` | Latest eviction rate per (region, sku) |
| `GET /v1/spot/detail` | `region` *(req)*, `sku` *(req)*, `osType?`, `snapshotDate?` | Composite: spot price + eviction rate + SKU catalog |

### V1 endpoints — Pricing analytics

| Path | Parameters | Description |
|---|---|---|
| `GET /v1/pricing/categories` | `limit?`, `cursor?` | Distinct pricing categories |
| `GET /v1/pricing/summary` | `region?[]`, `category?[]`, `priceType?[]`, `snapshotSince?`, `limit?`, `cursor?` | Pre-aggregated price summaries (multi-value filters) |
| `GET /v1/pricing/summary/latest` | `region?[]`, `category?[]`, `priceType?[]`, `limit?`, `cursor?` | Price summaries from latest run |
| `GET /v1/pricing/summary/series` | `region` *(req)*, `priceType` *(req)*, `bucket` *(req)*, `metric?`, `category?` | Time-bucketed pricing metric evolution |
| `GET /v1/pricing/summary/cheapest` | `priceType?`, `metric?`, `category?`, `limit?` | Top N cheapest regions from latest run |
| `GET /v1/pricing/summary/compare` | `regions[]` *(req)*, `priceType?`, `category?` | Compare pricing summaries across regions |

### V1 endpoints — SKU catalog & operations

| Path | Parameters | Description |
|---|---|---|
| `GET /v1/skus/catalog` | `search?`, `category?`, `family?`, `minVcpus?`, `maxVcpus?`, `limit?`, `cursor?` | VM SKU catalog with filters |
| `GET /v1/jobs` | `dataset?`, `status?`, `limit?`, `cursor?` | Ingestion job runs (newest first) |
| `GET /v1/jobs/{run_id}/logs` | `level?`, `limit?`, `cursor?` | Logs for a specific job run |

> V1 endpoints use keyset pagination (`limit` default 1000, max 5000 + `cursor`) unless noted.

## Related Repositories

| Repository | Description |
|---|---|
| [az-scout](https://github.com/lrivallain/az-scout) | Core application — FastAPI backend, MCP server, plugin framework |
| [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api) | Standalone REST API serving pricing data from PostgreSQL |
| [az-scout-bdd-ingestion](https://github.com/rsabile/az-scout-bdd-ingestion) | Data pipeline — ingestion, SKU enrichment, price aggregation, Terraform infra |
