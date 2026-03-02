"""Tests for advisory lock helpers."""

from az_scout_plugin_bdd_sku.service.locks import compute_lock_key


class TestComputeLockKey:
    """Tests for compute_lock_key."""

    def test_deterministic(self) -> None:
        k1 = compute_lock_key("retail", "USD", "tenant1")
        k2 = compute_lock_key("retail", "USD", "tenant1")
        assert k1 == k2

    def test_different_inputs(self) -> None:
        k1 = compute_lock_key("retail", "USD", "tenant1")
        k2 = compute_lock_key("spot", "linux", "tenant1")
        assert k1 != k2

    def test_returns_positive_int(self) -> None:
        k = compute_lock_key("test")
        assert isinstance(k, int)
        assert k >= 0
