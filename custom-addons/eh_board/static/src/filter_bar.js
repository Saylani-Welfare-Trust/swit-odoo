/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * The global filter bar: relative-date presets resolved on the client (so the
 * viewer's timezone always wins) into a {start, end} the board applies to
 * every time-based item at once. */

import { Component } from "@odoo/owl";

export const DATE_PRESETS = [
    { key: "all", label: "None" },
    { key: "today", label: "Today" },
    { key: "this_week", label: "This week" },
    { key: "this_month", label: "This month" },
    { key: "this_quarter", label: "This quarter" },
    { key: "this_year", label: "This year" },
    { key: "wtd", label: "Week to date" },
    { key: "mtd", label: "Month to date" },
    { key: "qtd", label: "Quarter to date" },
    { key: "ytd", label: "Year to date" },
    { key: "last_month", label: "Last month" },
    { key: "last_7", label: "Last 7 days" },
    { key: "last_30", label: "Last 30 days" },
    { key: "last_90", label: "Last 90 days" },
];

function iso(d) {
    // Format the LOCAL date components. NEVER toISOString(): it converts to UTC,
    // so for any positive-UTC-offset timezone (e.g. Australia, UTC+10/11) a local
    // midnight becomes the previous day and every preset ("today", "this month",
    // ...) silently returned the wrong range. The presets are resolved on the
    // client precisely so the viewer's own timezone wins.
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

export function resolvePreset(key) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth(), d = now.getDate();
    const startOfDay = new Date(y, m, d);
    const mk = (a, b) => ({ start: iso(a), end: iso(b) });
    switch (key) {
        case "today":
            return mk(startOfDay, startOfDay);
        case "this_week":
        case "wtd": {
            const dow = (now.getDay() + 6) % 7; // Monday-based
            return mk(new Date(y, m, d - dow), now);
        }
        case "this_month":
        case "mtd":
            return mk(new Date(y, m, 1), now);
        case "last_month":
            return mk(new Date(y, m - 1, 1), new Date(y, m, 0));
        case "this_quarter":
        case "qtd": {
            const q = Math.floor(m / 3) * 3;
            return mk(new Date(y, q, 1), now);
        }
        case "this_year":
        case "ytd":
            return mk(new Date(y, 0, 1), now);
        case "last_7":
            return mk(new Date(y, m, d - 6), now);
        case "last_30":
            return mk(new Date(y, m, d - 29), now);
        case "last_90":
            return mk(new Date(y, m, d - 89), now);
        default:
            return null;
    }
}

export class FilterBar extends Component {
    static template = "eh_board.FilterBar";
    static props = {
        preset: String,
        onPresetChange: Function,
        filters: { type: Array, optional: true },
        filterValues: { type: Object, optional: true },
        onFilterChange: { type: Function, optional: true },
    };

    presets = DATE_PRESETS;

    get fieldFilters() {
        return (this.props.filters || []).filter((f) => f.type === "field");
    }
    valueOf(filter) {
        const v = (this.props.filterValues || {})[filter.id];
        return v && v.length ? v[0] : "";
    }
    isSelected(filter, value) {
        return String(value) === String(this.valueOf(filter));
    }
    onSelect(ev) {
        this.props.onPresetChange(ev.target.value);
    }
    onFieldSelect(filter, ev) {
        const raw = ev.target.value;
        if (!this.props.onFilterChange) return;
        if (raw === "") {
            this.props.onFilterChange(filter.id, []);
        } else {
            // preserve the option's original type (id numbers vs strings)
            const opt = filter.options.find((o) => String(o.value) === raw);
            this.props.onFilterChange(filter.id, [opt ? opt.value : raw]);
        }
    }
}
