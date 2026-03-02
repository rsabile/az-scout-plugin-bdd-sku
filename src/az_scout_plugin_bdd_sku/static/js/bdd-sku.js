/**
 * BDD SKU plugin — SKU DB Cache tab logic.
 *
 * Loads the HTML fragment, wires buttons, and polls the plugin API
 * for cache status and warm operation results.
 */
(function () {
    "use strict";

    const PLUGIN_BASE = "/plugins/bdd-sku";
    const container = document.getElementById("plugin-tab-bdd-sku");
    if (!container) return;

    let logEl = null;

    // ── Helpers ──────────────────────────────────────────────────────

    function log(msg) {
        if (!logEl) return;
        const ts = new Date().toLocaleTimeString();
        logEl.textContent += `[${ts}] ${msg}\n`;
        logEl.parentElement.scrollTop = logEl.parentElement.scrollHeight;
    }

    function showError(msg) {
        const el = container.querySelector("#bdd-error");
        if (!el) return;
        el.textContent = msg;
        el.classList.remove("d-none");
    }

    function clearError() {
        const el = container.querySelector("#bdd-error");
        if (el) el.classList.add("d-none");
    }

    function setLoading(btn, loading) {
        if (loading) {
            btn.classList.add("bdd-loading");
            btn.disabled = true;
        } else {
            btn.classList.remove("bdd-loading");
            btn.disabled = false;
        }
    }

    function getAdvancedParams() {
        const skuEl = container.querySelector("#bdd-sku-sample");
        const subEl = container.querySelector("#bdd-subscriptions");
        const params = {};
        if (skuEl && skuEl.value.trim()) {
            params.sku_sample = skuEl.value.split(",").map(s => s.trim()).filter(Boolean);
        }
        if (subEl && subEl.value.trim()) {
            params.subscriptions = subEl.value.split(",").map(s => s.trim()).filter(Boolean);
        }
        return params;
    }

    // ── Status rendering ────────────────────────────────────────────

    function renderStatus(data) {
        // Retail
        const retailEl = container.querySelector("#bdd-status-retail");
        if (retailEl && data.retail) {
            const r = data.retail;
            const freshPct = r.total > 0 ? Math.round((r.fresh / r.total) * 100) : 0;
            const freshClass = freshPct > 80 ? "bdd-fresh" : "bdd-stale";
            retailEl.innerHTML = `
                <div class="bdd-stat"><span class="bdd-stat-label">Records</span>
                    <span class="bdd-stat-value">${r.total}</span></div>
                <div class="bdd-stat"><span class="bdd-stat-label">Fresh</span>
                    <span class="bdd-stat-value ${freshClass}">${r.fresh} (${freshPct}%)</span></div>
                <div class="bdd-stat"><span class="bdd-stat-label">Latest fetch</span>
                    <span class="bdd-stat-value">${formatTs(r.latest_fetched)}</span></div>
            `;
        }

        // Spot history
        const spotEl = container.querySelector("#bdd-status-spot");
        if (spotEl && data.spot_history) {
            const s = data.spot_history;
            spotEl.innerHTML = `
                <div class="bdd-stat"><span class="bdd-stat-label">Points</span>
                    <span class="bdd-stat-value">${s.total}</span></div>
                <div class="bdd-stat"><span class="bdd-stat-label">Latest point</span>
                    <span class="bdd-stat-value">${formatTs(s.latest_ts)}</span></div>
                <div class="bdd-stat"><span class="bdd-stat-label">Last ingested</span>
                    <span class="bdd-stat-value">${formatTs(s.latest_ingested)}</span></div>
            `;
        }

        // Eviction
        const evictEl = container.querySelector("#bdd-status-eviction");
        if (evictEl && data.eviction) {
            const e = data.eviction;
            evictEl.innerHTML = `
                <div class="bdd-stat"><span class="bdd-stat-label">Records</span>
                    <span class="bdd-stat-value">${e.total}</span></div>
                <div class="bdd-stat"><span class="bdd-stat-label">Latest observed</span>
                    <span class="bdd-stat-value">${formatTs(e.latest_observed)}</span></div>
            `;
        }
    }

    function formatTs(ts) {
        if (!ts) return "—";
        try {
            const d = new Date(ts);
            return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
        } catch {
            return ts;
        }
    }

    // ── API calls ───────────────────────────────────────────────────

    async function refreshStatus() {
        clearError();
        try {
            const resp = await apiFetch(`${PLUGIN_BASE}/status`);
            renderStatus(resp);
            log("Status refreshed");
        } catch (err) {
            showError(`Failed to load status: ${err.message}`);
            log(`ERROR: ${err.message}`);
        }
    }

    async function warmRetail() {
        const btn = container.querySelector("#bdd-warm-retail");
        if (!btn) return;
        clearError();
        setLoading(btn, true);
        log("Starting retail pricing warm…");

        const currency = container.querySelector("#bdd-currency")?.value || "USD";
        const tenant = document.getElementById("tenant-select")?.value || "";
        const body = {
            currency,
            ...getAdvancedParams(),
        };
        if (tenant) body.tenant_id = tenant;

        try {
            const result = await apiPost(`${PLUGIN_BASE}/warm/retail`, body);
            log(`Retail warm done: ${result.inserted} inserted, ${result.updated} updated, ` +
                `${result.skipped_fresh} skipped (fresh), ${(result.errors || []).length} errors`);
            if (result.errors && result.errors.length > 0) {
                for (const e of result.errors.slice(0, 5)) {
                    log(`  ⚠ ${e.source}: ${e.message}`);
                }
                if (result.errors.length > 5) {
                    log(`  … and ${result.errors.length - 5} more errors`);
                }
            }
            await refreshStatus();
        } catch (err) {
            showError(`Retail warm failed: ${err.message}`);
            log(`ERROR: ${err.message}`);
        } finally {
            setLoading(btn, false);
        }
    }

    async function warmSpot() {
        const btn = container.querySelector("#bdd-warm-spot");
        if (!btn) return;
        clearError();
        setLoading(btn, true);
        log("Starting spot cache warm (history + eviction)…");

        const osType = container.querySelector("#bdd-os-type")?.value || "linux";
        const tenant = document.getElementById("tenant-select")?.value || "";
        const body = {
            os_type: osType,
            ...getAdvancedParams(),
        };
        if (tenant) body.tenant_id = tenant;

        try {
            const result = await apiPost(`${PLUGIN_BASE}/warm/spot`, body);
            log(`Spot warm done: ${result.inserted} history points, ${result.updated} eviction, ` +
                `${(result.errors || []).length} errors`);
            if (result.errors && result.errors.length > 0) {
                for (const e of result.errors.slice(0, 5)) {
                    log(`  ⚠ ${e.source}: ${e.message}`);
                }
            }
            await refreshStatus();
        } catch (err) {
            showError(`Spot warm failed: ${err.message}`);
            log(`ERROR: ${err.message}`);
        } finally {
            setLoading(btn, false);
        }
    }

    // ── Initialization ──────────────────────────────────────────────

    async function init() {
        // Load HTML fragment
        try {
            const resp = await fetch(`${PLUGIN_BASE}/static/html/bdd-sku.html`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            container.innerHTML = await resp.text();
        } catch (err) {
            container.innerHTML = `<div class="alert alert-danger">
                Failed to load BDD SKU tab: ${err.message}</div>`;
            return;
        }

        logEl = container.querySelector("#bdd-log");

        // Wire buttons
        container.querySelector("#bdd-warm-retail")
            ?.addEventListener("click", warmRetail);
        container.querySelector("#bdd-warm-spot")
            ?.addEventListener("click", warmSpot);
        container.querySelector("#bdd-refresh-status")
            ?.addEventListener("click", refreshStatus);
        container.querySelector("#bdd-clear-log")
            ?.addEventListener("click", () => { if (logEl) logEl.textContent = ""; });

        // Listen for tenant changes
        document.getElementById("tenant-select")
            ?.addEventListener("change", refreshStatus);

        // Initial status load
        await refreshStatus();
        log("BDD SKU tab ready");
    }

    init();
})();
