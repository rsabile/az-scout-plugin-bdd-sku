// SKU DB Cache plugin tab logic
(function () {
    const PLUGIN = "bdd-sku";
    const container = document.getElementById("plugin-tab-" + PLUGIN);
    if (!container) return;

    // ---------------------------------------------------------------
    // 1. Load HTML fragment
    // ---------------------------------------------------------------
    fetch(`/plugins/${PLUGIN}/static/html/bdd-sku-tab.html`)
        .then(r => r.text())
        .then(html => { container.innerHTML = html; init(); })
        .catch(err => {
            container.innerHTML = `<div class="alert alert-danger">Failed to load plugin UI: ${err.message}</div>`;
        });

    // ---------------------------------------------------------------
    // 2. Init
    // ---------------------------------------------------------------
    function init() {
        async function refresh() {
            try {
                const data = await apiFetch(`/plugins/${PLUGIN}/status`);
                updateCard(data);
            } catch (e) {
                setBadge("error", "Error");
                setMeta(`<dd>${e.message}</dd>`);
            }
        }

        function setBadge(cls, text) {
            const el = document.getElementById("bdd-sku-badge-retail");
            if (!el) return;
            el.className = `bdd-sku-badge bdd-sku-badge--${cls}`;
            el.textContent = text;
        }

        function setMeta(html) {
            const el = document.getElementById("bdd-sku-meta-retail");
            if (el) el.innerHTML = html;
        }

        function updateCard(data) {
            const count = data.retail_prices_count ?? -1;
            const lr = data.last_run;

            let status = "idle";
            if (lr) {
                status = lr.status || "idle";
            }

            const labelMap = { ok: "Ready", running: "Loading…", error: "Error", idle: "Idle" };
            setBadge(status, labelMap[status] || status);

            let metaHtml = `<dt>Rows</dt><dd>${count >= 0 ? count.toLocaleString() : "N/A"}</dd>`;
            if (lr) {
                if (lr.started_at_utc) {
                    metaHtml += `<dt>Last run</dt><dd>${new Date(lr.started_at_utc).toLocaleString()}</dd>`;
                }
                if (lr.items_written != null) {
                    metaHtml += `<dt>Written</dt><dd>${lr.items_written.toLocaleString()}</dd>`;
                }
                if (lr.error_message) {
                    metaHtml += `<dt>Error</dt><dd class="text-danger">${lr.error_message}</dd>`;
                }
            }
            setMeta(metaHtml);
        }

        // Refresh button
        const refreshBtn = document.getElementById("bdd-sku-refresh");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", refresh);
        }

        // Initial load
        refresh();
    }
})();
