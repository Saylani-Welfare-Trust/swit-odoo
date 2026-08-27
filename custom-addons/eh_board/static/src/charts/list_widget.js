/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Grouped list / table: one row per category, one column per measure. */

import { Component, markup } from "@odoo/owl";
import { formatCompact } from "./svg_util";
import { matchRule, textOn } from "../conditional";

export class ListWidget extends Component {
    static template = "eh_board.ListWidget";
    static props = { payload: Object, meta: { type: Object, optional: true }, onDrill: { type: Function, optional: true } };

    get measureKeys() {
        return this.props.payload.measure_keys || [];
    }
    get columns() {
        const series = this.props.payload.series || [];
        return series.map((s) => s.label);
    }
    get rules() {
        return (this.props.meta && this.props.meta.conditional_rules) || [];
    }
    get colMax() {
        const rows = this.props.payload.rows || [];
        const max = {};
        for (const k of this.measureKeys) {
            max[k] = Math.max(1, ...rows.map((r) => Math.abs(r.values[k] || 0)));
        }
        return max;
    }
    get rows() {
        const p = this.props.payload, cmax = this.colMax, rules = this.rules;
        return (p.rows || []).map((r, i) => ({
            index: i,
            label: r.labels && r.labels.length ? r.labels[0] : "",
            cells: this.measureKeys.map((k, ki) => {
                const v = r.values[k] || 0;
                const m = matchRule(rules, v, ki);
                let style = "", bar = 0, barColor = "";
                if (m && m.style === "fill") {
                    style = `background:${m.color};color:${textOn(m.color)};`;
                } else if (m && m.style === "bar") {
                    bar = Math.round((Math.abs(v) / cmax[k]) * 100);
                    barColor = m.color;
                } else if (m) {
                    style = `color:${m.color};font-weight:700;`;
                }
                return { text: formatCompact(v), style, bar, barColor };
            }),
        }));
    }
    onRowClick(row) {
        if (this.props.onDrill) {
            this.props.onDrill({ label: row.label, index: row.index });
        }
    }
}

export class ContentWidget extends Component {
    static template = "eh_board.ContentWidget";
    static props = {
        payload: Object,
        meta: { type: Object, optional: true },
        onDrill: { type: Function, optional: true },
    };

    get isTodo() {
        return (this.props.payload.type || "richtext") === "todo";
    }
    get html() {
        // Content is authored by Builders (a trusted role), so render it as
        // markup. Untrusted input never reaches this widget.
        return markup(this.props.payload.content || "");
    }
    get todoLines() {
        // Content is sanitized HTML from the rich editor (block elements + <br>),
        // NOT plain newlines - split on block boundaries and strip tags so each
        // checklist item is clean text instead of showing literal <p>/<div> tags.
        const html = this.props.payload.content || "";
        const doc = new DOMParser().parseFromString(
            html.replace(/<\/(p|div|li|h[1-6]|tr)>/gi, "\n").replace(/<br\s*\/?>/gi, "\n"),
            "text/html");
        return (doc.body.textContent || "")
            .split("\n").map((l) => l.trim()).filter(Boolean);
    }
}
