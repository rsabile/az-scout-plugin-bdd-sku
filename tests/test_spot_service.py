"""Tests for spot data service (mocked DB + HTTP + Azure auth)."""

from unittest.mock import MagicMock, patch

from az_scout_plugin_bdd_sku.service.spot_data import (
    _build_location_list,
    _build_sku_list,
    warm_spot_data,
)


class TestKqlHelpers:
    """Tests for KQL clause builders."""

    def test_build_sku_list(self) -> None:
        result = _build_sku_list(["standard_d2s_v5", "standard_f4s_v2"])
        assert "'standard_d2s_v5'" in result
        assert "'standard_f4s_v2'" in result

    def test_build_location_list(self) -> None:
        result = _build_location_list(["eastus", "westeurope"])
        assert "'eastus'" in result
        assert "'westeurope'" in result


class TestWarmSpotData:
    """Tests for warm_spot_data (fully mocked)."""

    @patch("az_scout_plugin_bdd_sku.service.spot_data._fetch_subscriptions")
    def test_warm_fails_without_subscriptions(
        self,
        mock_subs: MagicMock,
    ) -> None:
        mock_subs.return_value = []
        result = warm_spot_data()
        assert result.ok is False
        assert any("subscriptions" in e["source"] for e in result.errors)

    @patch("az_scout_plugin_bdd_sku.service.spot_data.release_advisory_lock")
    @patch("az_scout_plugin_bdd_sku.service.spot_data.try_advisory_lock", return_value=True)
    @patch("az_scout_plugin_bdd_sku.service.spot_data.finish_ingest_run")
    @patch("az_scout_plugin_bdd_sku.service.spot_data.create_ingest_run")
    @patch("az_scout_plugin_bdd_sku.service.spot_data.get_conn")
    @patch("az_scout_plugin_bdd_sku.service.spot_data.upsert_spot_eviction_rates", return_value=2)
    @patch("az_scout_plugin_bdd_sku.service.spot_data.upsert_spot_price_points", return_value=5)
    @patch("az_scout_plugin_bdd_sku.service.spot_data._query_eviction_rates")
    @patch("az_scout_plugin_bdd_sku.service.spot_data._query_spot_history")
    @patch("az_scout_plugin_bdd_sku.service.spot_data._get_token", return_value="fake-token")
    @patch("az_scout_plugin_bdd_sku.service.spot_data._fetch_subscriptions")
    def test_warm_ingests_data(
        self,
        mock_subs: MagicMock,
        mock_token: MagicMock,
        mock_history: MagicMock,
        mock_eviction: MagicMock,
        mock_upsert_points: MagicMock,
        mock_upsert_rates: MagicMock,
        mock_conn: MagicMock,
        mock_create: MagicMock,
        mock_finish: MagicMock,
        mock_lock: MagicMock,
        mock_unlock: MagicMock,
    ) -> None:
        import uuid

        mock_subs.return_value = ["sub-1"]
        mock_history.return_value = [
            {
                "skuName": "Standard_D2s_v5",
                "osType": "linux",
                "location": "eastus",
                "spotPrices": [
                    {"timestamp": "2026-01-01T00:00:00Z", "unitPrice": 0.012},
                    {"timestamp": "2026-01-02T00:00:00Z", "unitPrice": 0.013},
                ],
            }
        ]
        mock_eviction.return_value = [
            {
                "skuName": "Standard_D2s_v5",
                "location": "eastus",
                "spotEvictionRate": "0-5%",
            }
        ]
        mock_create.return_value = uuid.uuid4()

        mock_connection = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = warm_spot_data(
            locations=["eastus"],
            sku_sample=["standard_d2s_v5"],
        )

        assert result.dataset == "spot"
        assert result.regions_count == 1
        assert result.skus_count == 1
        # History points inserted
        assert result.inserted == 5
        # Eviction rates
        assert result.updated == 2

    @patch("az_scout_plugin_bdd_sku.service.spot_data._get_token")
    @patch("az_scout_plugin_bdd_sku.service.spot_data._fetch_subscriptions")
    def test_warm_handles_auth_failure(
        self,
        mock_subs: MagicMock,
        mock_token: MagicMock,
    ) -> None:
        mock_subs.return_value = ["sub-1"]
        mock_token.side_effect = Exception("Auth failed")

        result = warm_spot_data(locations=["eastus"])
        assert result.ok is False
        assert any("auth" in e["source"] for e in result.errors)
