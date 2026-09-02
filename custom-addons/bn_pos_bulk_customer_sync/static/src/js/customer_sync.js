/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CustomerCache } from "./customer_indexeddb";

// Loads gzip via the browser's native fetch decompression (most browsers
// auto-decompress a gzip Content-Encoding, but our controller sends the
// bytes as an opaque attachment, so we decompress with DecompressionStream
// where available and fall back to pako-less manual handling otherwise).
async function fetchSnapshotRecords() {
    const resp = await fetch("/pos_bulk_customer_sync/snapshot");
    if (!resp.ok) return null;
    const buf = await resp.arrayBuffer();

    let text;
    if (typeof DecompressionStream !== "undefined") {
        const ds = new DecompressionStream("gzip");
        const stream = new Blob([buf]).stream().pipeThrough(ds);
        text = await new Response(stream).text();
    } else {
        // Older browsers/webviews on some till hardware won't have
        // DecompressionStream - bundle a small gunzip lib (e.g. pako) as a
        // fallback if you need to support those.
        throw new Error(
            "DecompressionStream not supported on this device; add a pako fallback."
        );
    }
    return JSON.parse(text);
}

async function fetchDeltaPage(since, offset) {
    const resp = await fetch("/pos_bulk_customer_sync/delta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: { since, offset, limit: 5000 },
        }),
    });
    const json = await resp.json();
    return json.result;
}

export const BulkCustomerSync = {
    // Call once after the POS session UI is already interactive - never
    // block session open on this. Cashiers should be able to ring up a sale
    // (even without a named customer) while this runs in the background.
    async run(onProgress) {
        const lastFullSync = await CustomerCache.getMeta("last_full_sync");

        if (!lastFullSync) {
            // First run on this till: pull the pre-built nightly snapshot
            // instead of paging 500K rows live - keeps load off the server
            // even with 25 shops onboarding around the same time.
            const records = await fetchSnapshotRecords();
            if (records) {
                const CHUNK = 5000;
                for (let i = 0; i < records.length; i += CHUNK) {
                    const chunk = records.slice(i, i + CHUNK);
                    await CustomerCache.putMany(chunk);
                    onProgress?.(Math.min(i + CHUNK, records.length), records.length);
                    // Yield to the UI thread between chunks so the till stays
                    // responsive while this loads.
                    await new Promise((r) => setTimeout(r, 0));
                }
                const newestWriteDate = records.reduce(
                    (max, r) => (r.write_date > max ? r.write_date : max),
                    ""
                );
                await CustomerCache.setMeta("last_full_sync", newestWriteDate || new Date().toISOString());
            }
            return;
        }

        // Subsequent runs: only pull what changed since last sync.
        let since = lastFullSync;
        let offset = 0;
        let hasMore = true;
        while (hasMore) {
            const page = await fetchDeltaPage(since, offset);
            if (!page) break;
            await CustomerCache.putMany(page.records);
            await CustomerCache.deleteMany(page.removed_ids);
            hasMore = page.has_more;
            offset += page.records.length;
            const newest = page.records.reduce(
                (max, r) => (r.write_date > max ? r.write_date : max),
                since
            );
            since = newest;
        }
        await CustomerCache.setMeta("last_full_sync", since);
    },
};

// Odoo 17 POS boots the session through the service registry; wire this in
// as a service (or call BulkCustomerSync.run() from wherever your POS
// startup already fires off other post-load background tasks, e.g. next to
// the products background loader).
registry.category("services").add("pos_bulk_customer_sync", {
    dependencies: [],
    start() {
        // Fire and forget, after a short delay so it doesn't compete with
        // initial screen paint / product loading.
        setTimeout(() => BulkCustomerSync.run(), 1500);
        return BulkCustomerSync;
    },
});
