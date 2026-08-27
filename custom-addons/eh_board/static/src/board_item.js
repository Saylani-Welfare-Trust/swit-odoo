/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * The host for one widget: title, a hover toolbar (export, fullscreen,
 * configure, remove), and the resolved chart component - plus the states the
 * incumbents skip (skeleton, empty, and an error that explains itself). */

import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatCompact } from "./charts/svg_util";
import { hideTooltip } from "./charts/tooltip";
import { csvCell, csvRow } from "./csv";

/** Copy computed fill/stroke/font from a live SVG subtree onto its clone, so a
 *  serialized export keeps its colours (CSS custom properties are resolved). */
function inlineSvgStyles(src, dst) {
    const cs = getComputedStyle(src);
    for (const p of ["fill", "stroke", "stroke-width", "font-size", "font-family",
        "font-weight", "opacity", "fill-opacity", "stroke-linecap", "text-anchor"]) {
        const v = cs.getPropertyValue(p);
        if (v) dst.style.setProperty(p, v);
    }
    const sc = src.children, dc = dst.children;
    for (let i = 0; i < sc.length && i < dc.length; i++) inlineSvgStyles(sc[i], dc[i]);
}

export class BoardItem extends Component {
    static template = "eh_board.BoardItem";
    static props = {
        meta: Object,
        payload: [Object, { value: null }],
        editMode: { type: Boolean, optional: true },
        loading: { type: Boolean, optional: true },
        onDrill: { type: Function, optional: true },
        crossFilters: { type: Array, optional: true },
        drillPath: { type: Array, optional: true },
        onDrillUp: { type: Function, optional: true },
        onConfigure: { type: Function, optional: true },
        onRemove: { type: Function, optional: true },
        onDuplicate: { type: Function, optional: true },
    };

    get breadcrumb() {
        // Root crumb plus one per drilled level; used to climb back up.
        const path = this.props.drillPath || [];
        if (!path.length) return [];
        return [{ label: this.props.meta.title || "All", level: 0 }].concat(
            path.map((p, i) => ({ label: p.label, level: i + 1 })));
    }
    drillTo(level) {
        if (this.props.onDrillUp) this.props.onDrillUp(level);
    }

    setup() {
        this.state = useState({ fullscreen: false });
        this.widgetRef = useRef("widget");
        // Kill the shared cursor tooltip if this widget unmounts (refresh /
        // drill / remove) while a mark is hovered - otherwise it freezes over
        // the new content and leaks the DOM node.
        onWillUnmount(() => hideTooltip());
    }
    onLeaveWidget() {
        hideTooltip();
    }

    // -- accessibility: a real data table behind every chart -----------------
    // A visually-hidden but focusable table gives screen-reader users the
    // figures the SVG cannot convey, and its rows are keyboard-operable (Enter
    // drills exactly like clicking the mark) - so "screen-reader data table" and
    // "keyboard operation" are true, from one place, for every chart type.
    get srTable() {
        const p = this.props.payload;
        if (!p || this.error || p.category === "content") return null;
        // Any single-value widget (KPI, tile, gauge, bullet) - some carry
        // category "chart", so key off the presence of a value, not the category,
        // or the gauge/bullet charts would render NO screen-reader table and break
        // the "data table behind every chart" promise.
        if (p.value !== undefined) {
            const headers = ["Value"];
            const cells = [formatCompact(p.value || 0)];
            if (p.target !== undefined && p.target) {
                headers.push("Target");
                cells.push(formatCompact(p.target));
            }
            return { headers, rows: [{ label: "", cells, index: 0, drill: false }] };
        }
        const rows = p.rows || [];
        const series = p.series || [];
        const keys = p.measure_keys || [];
        if (!rows.length || !keys.length) return null;
        const canDrill = this.props.meta.category === "chart" || this.props.meta.category === "kpi";
        return {
            headers: series.length ? series.map((s) => s.label) : keys,
            rows: rows.slice(0, 200).map((r, i) => ({
                label: (r.labels && r.labels[0]) || "",
                cells: keys.map((k) => formatCompact((r.values && r.values[k]) || 0)),
                index: i,
                drill: canDrill,
            })),
        };
    }
    srDrill(row) {
        if (row.drill && this.props.onDrill) {
            this.props.onDrill({ label: row.label, index: row.index });
        }
    }

    get isChart() {
        const c = this.props.meta.category;
        return c === "chart" || c === "kpi";
    }
    // PNG export only makes sense for the SVG-rendered chart types; the HTML
    // widgets (tile, kpi, bullet, list, pivot, heatmap, slicer, decomp) have no
    // <svg>, so the picture button must not show for them.
    get hasSvg() {
        // SVG-rendered types only (the heatmap/pivot/list are HTML tables). The
        // choropleth map IS an SVG, so it is included - the flagship chart was
        // wrongly excluded from "PNG of any chart".
        return ["bar", "hbar", "column", "line", "area", "pie", "doughnut", "radar",
                "polar", "radial", "rose", "funnel", "pyramid", "scatter", "gauge",
                "map"]
            .includes(this.props.meta.type);
    }

    get component() {
        const key = this.props.meta.component || this.props.meta.type;
        return registry.category("eh_board_items").get(key, null);
    }
    get error() {
        return this.props.payload && this.props.payload.error;
    }
    get warning() {
        // A non-blocking notice (e.g. a file source truncated at the row cap):
        // the widget still renders, but the figures are flagged as partial.
        return this.props.payload && this.props.payload.warning;
    }
    get isEmpty() {
        const p = this.props.payload;
        if (!p || this.error) return false;
        // KPI / content / slicer (control) render their own shape, not series.
        if (p.category === "kpi" || p.category === "content" || p.category === "control") return false;
        // Single-value widgets (KPI / gauge / bullet) always have their value.
        if (p.value !== undefined) return false;
        // The decomposition tree carries its data in level0.nodes, not series.
        if (p.level0) return !((p.level0.nodes || []).length);
        // Table-shaped widgets carry data in rows / row_headers, not series.
        if (p.category === "pivot") return !(p.row_headers && p.row_headers.length);
        if (p.category === "table") return !(p.rows && p.rows.length);
        // A chart with categories but zero values is valid data (a zero-sales
        // month) - NOT empty. Empty means no categories / no data points at all.
        const hasCats = (p.labels && p.labels.length) ||
            (p.series || []).some((s) => (s.data || []).length);
        return !hasCats;
    }
    get canExport() {
        const p = this.props.payload;
        return p && !this.error && p.category !== "content";
    }
    get childProps() {
        const props = {
            payload: this.props.payload || {},
            meta: this.props.meta,
            onDrill: this.props.onDrill,
        };
        // Only the slicer consumes the live cross-filters (strict props elsewhere).
        if (this.props.meta.component === "slicer") {
            props.crossFilters = this.props.crossFilters || [];
        }
        return props;
    }

    toggleFullscreen() {
        this.state.fullscreen = !this.state.fullscreen;
    }

    exportItem() {
        const p = this.props.payload;
        const title = this.props.meta.title || this.props.meta.type;
        const lines = [csvCell(title)];
        // Any single-value widget (KPI / tile / gauge / bullet) exports its value.
        if (p.value !== undefined) {
            lines.push(csvRow(["value", p.value || 0]));
        } else if (p.rows) {
            const keys = p.measure_keys || [];
            lines.push(csvRow(["category", ...(p.series || []).map((s) => s.label)]));
            p.rows.forEach((r) => {
                // Join every dimension label so a two-dimension widget keeps both
                // dimensions instead of collapsing to an ambiguous first label.
                const label = (r.labels || []).filter(
                    (l) => l !== null && l !== undefined && l !== "").join(" / ");
                lines.push(csvRow([label, ...keys.map((k) => r.values[k] || 0)]));
            });
        }
        this._download(new Blob([lines.join("\n")], { type: "text/csv" }), `${title}.csv`);
    }

    exportPng() {
        const root = this.widgetRef.el;
        const svg = root && root.querySelector("svg");
        const title = this.props.meta.title || this.props.meta.type;
        if (!svg) {
            return;  // no <svg> to rasterise; never silently download a CSV instead
        }
        const rect = svg.getBoundingClientRect();
        const w = Math.max(320, Math.round(rect.width));
        const h = Math.max(200, Math.round(rect.height));
        const clone = svg.cloneNode(true);
        inlineSvgStyles(svg, clone);
        clone.setAttribute("width", w);
        clone.setAttribute("height", h);
        const xml = new XMLSerializer().serializeToString(clone);
        const src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
        const img = new Image();
        img.onload = () => {
            const scale = 2;
            const canvas = document.createElement("canvas");
            canvas.width = w * scale;
            canvas.height = h * scale;
            const ctx = canvas.getContext("2d");
            const bg = getComputedStyle(root).getPropertyValue("--eh-board-surface") || "#fff";
            ctx.fillStyle = bg.trim() || "#fff";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            canvas.toBlob((blob) => this._download(blob, `${title}.png`), "image/png");
        };
        // A malformed / tainted SVG (e.g. an external reference) would otherwise
        // fail silently; surface nothing dangerous but do not hang on a dead load.
        img.onerror = () => { /* export unavailable for this chart; no-op */ };
        img.src = src;
    }

    _download(blob, name) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
    }
}
