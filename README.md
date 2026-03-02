# az-scout-bdd-sku

An [az-scout](https://github.com/lrivallain/az-scout) plugin that provides a
persistent **PostgreSQL-backed cache** for:

- **VM retail pricing** per region + SKU (via core `/api/sku-pricing`)
- **Spot eviction rates** per region + SKU (via Azure Resource Graph)
- **Spot price history** points per region + SKU (via Azure Resource Graph)

## Features

- **SKU DB Cache** UI tab with warm controls, status cards, and activity log
- **REST endpoints** for cache status, warm operations, and run tracking
- **5 MCP tools** for LLM-friendly access to cached pricing data
- **Anti-stampede** protection via PostgreSQL advisory locks
- **Configurable TTL** for cache freshness (default 12 hours)
- **Dark/light theme** support

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL 16 (local or Docker)
- Azure credentials (`az login` or service principal for ARG queries)
- A running az-scout instance

## Quick Start

### 1. Start PostgreSQL

```bash
cd dev
docker compose up -d
```

This starts PostgreSQL 16 on port 5432 with the schema auto-applied.

### 2. Configure the plugin

```bash
cp dev/plugin-config.example.toml ~/.config/az-scout/bdd-sku.toml
# Edit the file if your PostgreSQL DSN differs from the default
```

Or set the environment variable:

```bash
export AZ_SCOUT_BDD_SKU_CONFIG=/path/to/bdd-sku.toml
```

### 3. Install the plugin

```bash
# From the plugin repo root
uv pip install -e .
```

### 4. Start az-scout

```bash
# The plugin is auto-discovered
az-scout web --reload
```

Navigate to the **SKU DB Cache** tab in the UI.

## Configuration

The plugin reads from `~/.config/az-scout/bdd-sku.toml` (or the path in
`AZ_SCOUT_BDD_SKU_CONFIG`).

```toml
[database]
dsn = "postgresql://bddsku:bddsku@localhost:5432/bddsku"
pool_min = 2
pool_max = 10

[cache]
retail_ttl_hours = 12
```

## API Endpoints

All endpoints are mounted under `/plugins/bdd-sku/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Cache statistics and recent ingest runs |
| POST | `/warm/retail` | Trigger retail pricing warm (body: `currency`, `skus`) |
| POST | `/warm/spot` | Trigger spot data warm (body: `regions`, `os_type`) |
| GET | `/runs/{run_id}` | Get details of a specific ingest run |

## MCP Tools

| Tool | Description |
|------|-------------|
| `cache_status` | Get cache statistics |
| `retail_price_get` | Get cached retail price for a specific region + SKU |
| `retail_prices_query` | Query cached retail prices with filters |
| `spot_eviction_rates_query` | Query cached spot eviction rates |
| `spot_price_series` | Get spot price history for a SKU + region |

## Development

### Run tests

```bash
uv run pytest
```

### Lint and type check

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
```

## Structure

```
az-scout-example/
├── .github/
│   ├── copilot-instructions.md  # Copilot context for this plugin
│   └── workflows/
```
src/az_scout_plugin_bdd_sku/
├── __init__.py              # Plugin entry point (BddSkuPlugin)
├── config.py                # TOML config loader
├── db.py                    # PostgreSQL connection pool + queries
├── models.py                # Typed dataclasses
├── mcp_tools.py             # 5 MCP tools
├── routes.py                # FastAPI router (4 endpoints)
├── service/
│   ├── locks.py             # Advisory lock key computation
│   ├── retail_pricing.py    # Retail warm + fetch logic
│   └── spot_data.py         # ARG queries + spot ingestion
├── sql/
│   └── schema.sql           # PostgreSQL schema (4 tables)
└── static/
    ├── css/bdd-sku.css
    ├── html/bdd-sku.html
    └── js/bdd-sku.js
dev/
├── docker-compose.yml        # PostgreSQL 16 dev container
└── plugin-config.example.toml
tests/
├── test_config.py
├── test_locks.py
├── test_mcp_tools.py
├── test_retail_service.py
├── test_routes.py
└── test_spot_service.py
```

## License

MIT — see [LICENSE.txt](LICENSE.txt).

