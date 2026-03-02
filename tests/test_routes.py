"""Tests for FastAPI routes (mocked DB layer)."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from az_scout_plugin_bdd_sku.routes import router

app = FastAPI()
app.include_router(router, prefix="/plugins/bdd-sku")
client = TestClient(app)


class TestStatusEndpoint:
    """Tests for GET /plugins/bdd-sku/status."""

    @patch("az_scout_plugin_bdd_sku.routes.get_conn")
    @patch("az_scout_plugin_bdd_sku.routes.get_cache_status")
    def test_returns_status(
        self,
        mock_status: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        mock_status.return_value = {
            "retail": {"total": 100, "fresh": 80, "earliest_fetched": None, "latest_fetched": None},
            "spot_history": {
                "total": 500,
                "earliest_ts": None,
                "latest_ts": None,
                "latest_ingested": None,
            },
            "eviction": {"total": 50, "latest_observed": None},
            "last_runs": [],
        }
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/plugins/bdd-sku/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "retail" in data
        assert data["retail"]["total"] == 100
        assert "spot_history" in data
        assert "eviction" in data


class TestWarmRetailEndpoint:
    """Tests for POST /plugins/bdd-sku/warm/retail."""

    def test_warm_retail_calls_service(self) -> None:
        from az_scout_plugin_bdd_sku.models import WarmResult

        mock_warm = MagicMock(
            return_value=WarmResult(
                ok=True,
                dataset="retail",
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:01:00Z",
                regions_count=5,
                skus_count=8,
                inserted=40,
            ),
        )

        with patch(
            "az_scout_plugin_bdd_sku.service.retail_pricing.warm_retail_pricing",
            mock_warm,
        ):
            resp = client.post(
                "/plugins/bdd-sku/warm/retail",
                json={"currency": "USD"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset"] == "retail"


class TestWarmSpotEndpoint:
    """Tests for POST /plugins/bdd-sku/warm/spot."""

    def test_warm_spot_calls_service(self) -> None:
        from az_scout_plugin_bdd_sku.models import WarmResult

        mock_warm = MagicMock(
            return_value=WarmResult(
                ok=True,
                dataset="spot",
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:02:00Z",
                inserted=100,
                updated=20,
            ),
        )

        with patch(
            "az_scout_plugin_bdd_sku.service.spot_data.warm_spot_data",
            mock_warm,
        ):
            resp = client.post(
                "/plugins/bdd-sku/warm/spot",
                json={"os_type": "linux"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset"] == "spot"


class TestRunEndpoint:
    """Tests for GET /plugins/bdd-sku/runs/{run_id}."""

    @patch("az_scout_plugin_bdd_sku.routes.get_conn")
    @patch("az_scout_plugin_bdd_sku.routes.get_ingest_run")
    def test_returns_run(
        self,
        mock_run: MagicMock,
        mock_conn: MagicMock,
    ) -> None:
        import uuid

        run_id = uuid.uuid4()
        mock_run.return_value = {
            "run_id": str(run_id),
            "dataset": "retail",
            "status": "ok",
            "started_at_utc": None,
            "finished_at_utc": None,
            "details": None,
        }
        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get(f"/plugins/bdd-sku/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset"] == "retail"

    def test_invalid_run_id(self) -> None:
        resp = client.get("/plugins/bdd-sku/runs/not-a-uuid")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
