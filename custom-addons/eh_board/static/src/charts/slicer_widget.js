/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * On-canvas slicer: a field's values as chips. Clicking a chip cross-filters
 * every widget on the board (reuses the onDrill channel with a `slice` payload,
 * so no extra callback plumbing). Active chips reflect the live cross-filters. */

import { Component, useState } from "@odoo/owl";

export class SlicerWidget extends Component {
    static template = "eh_board.SlicerWidget";
    static props = {
        payload: Object,
        meta: { type: Object, optional: true },
        onDrill: { type: Function, optional: true },
        crossFilters: { type: Array, optional: true },
    };

    setup() {
        this.state = useState({ search: "" });
    }
    get field() { return this.props.payload.field; }
    get values() { return this.props.payload.values || []; }
    get filteredValues() {
        const q = (this.state.search || "").toLowerCase().trim();
        if (!q) return this.values;
        return this.values.filter((v) => String(v.label).toLowerCase().includes(q));
    }
    get activeKeys() {
        const cf = this.props.crossFilters || [];
        return new Set(cf.filter((c) => c.field === this.field).map((c) => String(c.value)));
    }
    get hasActive() { return this.activeKeys.size > 0; }
    isActive(v) { return this.activeKeys.has(String(v.key)); }
    toggle(v) {
        if (this.props.onDrill) {
            this.props.onDrill({ slice: { field: this.field, value: v.key, label: v.label } });
        }
    }
    clearAll() {
        // Toggle off every currently-active value for this slicer's field.
        this.values.filter((v) => this.isActive(v)).forEach((v) => this.toggle(v));
    }
}
