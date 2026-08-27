/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Pivot / cross-tab matrix widget. Renders measures against row and column
 * dimensions with row/column subtotals and a grand total. All shaping is done
 * server-side; this component only lays out a ready matrix into an accessible
 * HTML table (real <table>, sticky header + first column, optional heat map,
 * click-through drill on any cell). No canvas, no external grid lib. */

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatValue } from "./svg_util";
import { matchRule, textOn } from "../conditional";

export class PivotWidget extends Component {
    static template = "eh_board.PivotWidget";
    static props = {
        payload: Object,
        meta: { type: Object, optional: true },
        onDrill: { type: Function, optional: true },
    };

    get p() {
        return this.props.payload || {};
    }
    get measureKeys() {
        return this.p.measure_keys || [];
    }
    get single() {
        return this.measureKeys.length === 1;
    }
    get hasCol() {
        return !!this.p.has_col && (this.p.col_headers || []).length > 0;
    }
    get heatOn() {
        return !!this.p.heatmap && this.single;
    }
    _mlabel(mk) {
        return (this.p.measure_labels || {})[mk] || mk;
    }
    _fmt(v) {
        return formatValue(v || 0, this.p.number_format || "compact");
    }
    _skey(k) {
        // Must agree with the Python _skey: null/undefined -> "∅"; booleans map
        // to lower-case "true"/"false" (String(true) already gives "true"), so a
        // boolean row matches its cells instead of rendering an all-zero row.
        if (k === null || k === undefined) return "∅";
        return String(k);
    }
    _cellVal(rks, cks, mk) {
        const row = (this.p.cells || {})[rks] || {};
        const c = row[cks] || {};
        return c[mk] || 0;
    }
    _heatStyle(v, max) {
        if (!this.heatOn || !max) return "";
        // Light -> saturated mint proportional to magnitude; keeps text legible.
        const t = Math.min(1, Math.abs(v) / max);
        const alpha = (0.06 + t * 0.42).toFixed(3);
        return `background: color-mix(in srgb, var(--eh-board-accent) ${Math.round(alpha * 100)}%, transparent);`;
    }
    get rules() {
        return (this.props.meta && this.props.meta.conditional_rules) || [];
    }
    _cellStyle(v, mk, heatMax) {
        // A matching colour rule wins over the heat map; else fall back to heat.
        const cond = matchRule(this.rules, v, this.measureKeys.indexOf(mk));
        if (cond) {
            return cond.style === "fill"
                ? `background:${cond.color};color:${textOn(cond.color)};`
                : `color:${cond.color};font-weight:700;`;
        }
        return this._heatStyle(v, heatMax);
    }

    /** The whole matrix, precomputed into header rows, body rows and a footer
     *  so the template is a plain triple t-foreach with no branching logic. */
    get grid() {
        const p = this.p;
        const mkeys = this.measureKeys;
        const single = this.single;
        const hasCol = this.hasCol;
        const cols = p.col_headers || [];
        const rows = p.row_headers || [];

        // Leaf body columns: (column value x measure) when there is a column
        // dimension, otherwise one per measure.
        const leaf = [];
        if (hasCol) {
            for (const c of cols) {
                for (const mk of mkeys) {
                    leaf.push({ cks: this._skey(c.key), mk, raw: c.key });
                }
            }
        } else {
            for (const mk of mkeys) leaf.push({ cks: "__m__", mk, raw: null });
        }

        // Header rows.
        const headerRows = [];
        const corner = { label: p.row_dim_label || "", corner: true, span: 1 };
        if (hasCol && !single) {
            const r1 = [corner];
            for (const c of cols) r1.push({ label: c.label, span: mkeys.length });
            r1.push({ label: _t("Total"), span: mkeys.length, total: true });
            const r2 = [{ label: "", corner: true, span: 1 }];
            for (let i = 0; i < cols.length; i++) {
                for (const mk of mkeys) r2.push({ label: this._mlabel(mk) });
            }
            for (const mk of mkeys) r2.push({ label: this._mlabel(mk), total: true });
            headerRows.push(r1, r2);
        } else if (hasCol && single) {
            const r1 = [corner];
            for (const c of cols) r1.push({ label: c.label });
            r1.push({ label: _t("Total"), total: true });
            headerRows.push(r1);
        } else {
            const r1 = [corner];
            for (const mk of mkeys) r1.push({ label: this._mlabel(mk) });
            headerRows.push(r1);
        }

        // Heat-map scale (single measure only).
        const maxByM = {};
        if (this.heatOn) {
            for (const mk of mkeys) {
                let mx = 0;
                for (const r of rows) {
                    const rks = this._skey(r.key);
                    const cc = hasCol ? cols : [{ key: "__m__" }];
                    for (const c of cc) {
                        const cks = hasCol ? this._skey(c.key) : "__m__";
                        mx = Math.max(mx, Math.abs(this._cellVal(rks, cks, mk)));
                    }
                }
                maxByM[mk] = mx || 1;
            }
        }

        // Body rows.
        const bodyRows = [];
        for (const r of rows) {
            const rks = this._skey(r.key);
            const cells = [];
            for (const lc of leaf) {
                const v = this._cellVal(rks, lc.cks, lc.mk);
                cells.push({
                    text: this._fmt(v), style: this._cellStyle(v, lc.mk, maxByM[lc.mk]),
                    drill: true, rowRaw: r.key, colRaw: lc.raw,
                });
            }
            if (hasCol) {
                for (const mk of mkeys) {
                    cells.push({ text: this._fmt((p.row_totals[rks] || {})[mk] || 0), total: true });
                }
            }
            bodyRows.push({ label: r.label, cells });
        }

        // Footer (column totals + grand total).
        const fcells = [];
        if (hasCol) {
            for (const lc of leaf) {
                fcells.push({ text: this._fmt((p.col_totals[lc.cks] || {})[lc.mk] || 0) });
            }
            for (const mk of mkeys) {
                fcells.push({ text: this._fmt(p.grand_total[mk] || 0), grand: true });
            }
        } else {
            for (const mk of mkeys) {
                fcells.push({ text: this._fmt(p.grand_total[mk] || 0), grand: true });
            }
        }
        const footer = { label: _t("Total"), cells: fcells };

        return { headerRows, bodyRows, footer };
    }

    onCellClick(row, cell) {
        if (!this.props.onDrill || !cell.drill) return;
        const domain = [];
        const rf = this.p.row_field, cf = this.p.col_field;
        if (rf) this._pushLeaf(domain, rf, this.p.row_field_type, cell.rowRaw);
        if (cf) this._pushLeaf(domain, cf, this.p.col_field_type, cell.colRaw);
        this.props.onDrill({ domain, label: row.label });
    }

    /** Push a domain leaf for a dimension value: a period range for a date/
     *  datetime bucket, an equality otherwise. */
    _pushLeaf(domain, field, ftype, raw) {
        if (raw === null || raw === undefined) {
            domain.push([field, "=", false]);
            return;
        }
        if ((ftype === "date" || ftype === "datetime") && typeof raw === "string") {
            const range = this._periodRange(raw, this.p.granularity);
            if (range) {
                domain.push([field, ">=", range.start], [field, "<", range.end]);
                return;
            }
        }
        domain.push([field, "=", raw]);
    }

    _periodRange(iso, granularity) {
        // Parse the bucket key as LOCAL date/time components (never new Date(iso),
        // which reads a date-only string as UTC and can shift the day), and format
        // the range back the same way - so no toISOString() UTC drift. An hour
        // bucket yields a datetime range; coarser buckets yield a date range.
        const m = String(iso).match(/(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}))?/);
        if (!m) return null;
        const hour = m[4] ? +m[4] : 0;
        const d = new Date(+m[1], +m[2] - 1, +m[3], hour);
        const e = new Date(d);
        switch (granularity) {
            case "hour": e.setHours(e.getHours() + 1); break;
            case "day": e.setDate(e.getDate() + 1); break;
            case "week": e.setDate(e.getDate() + 7); break;
            case "quarter": e.setMonth(e.getMonth() + 3); break;
            case "year": e.setFullYear(e.getFullYear() + 1); break;
            case "month":
            default: e.setMonth(e.getMonth() + 1); break;
        }
        const p = (n) => String(n).padStart(2, "0");
        const fmt = (x) => granularity === "hour"
            ? `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())} ${p(x.getHours())}:00:00`
            : `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}`;
        return { start: fmt(d), end: fmt(e) };
    }
}
