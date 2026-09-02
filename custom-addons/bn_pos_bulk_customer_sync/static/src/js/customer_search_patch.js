/** @odoo-module **/
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list_screen";
import { CustomerCache } from "./customer_indexeddb";

function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

patch(PartnerListScreen.prototype, "pos_bulk_customer_sync/partner_list", {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.bulk = useState({ results: [], busy: false });
        this._bulkSearch = debounce((q) => this._doBulkSearch(q), 200);
    },

    // Patch whatever your build's template iterates (getter `partners` in
    // most 17.0 builds; a method like getPartners() in others — check yours).
    get partners() {
        const query = (this.state.query || "").trim();
        if (query) {
            this._bulkSearch(query);        // async; re-renders when results land
            return this.bulk.results;
        }
        return super.partners;
    },

    async _doBulkSearch(query) {
        const digits = query.replace(/[^0-9+]/g, "");
        let matches = digits.length >= 3
            ? await CustomerCache.findByPhonePrefix(digits)
            : query.length >= 2
                ? await CustomerCache.findByNamePrefix(query.toLowerCase())
                : [];
        if ((this.state.query || "").trim() !== query) return; // stale response
        if (navigator.onLine && matches.length) {
            matches = await this._materialize(matches.slice(0, 30));
        }
        this.bulk.results = matches;
    },

    async _materialize(slim) {
        const ids = slim.map((r) => r.id);
        try {
            const full = await this.orm.call("res.partner", "read", [ids]);
            // ⚠ verify this against YOUR 17.0.x source: check how the partner
            // edit screen's save handler (or data_store.js) inserts a new
            // res.partner into the store, and use the same call, e.g.:
            this.pos.models["res.partner"].add(full);
            return this.pos.getRecords("res.partner", [["id", "in", ids]]);
        } catch {
            return slim; // offline fallback: slim objects (selection may be limited)
        }
    },
});