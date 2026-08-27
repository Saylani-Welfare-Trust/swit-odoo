/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * One parametric Cartesian chart for bar, horizontal bar, stacked column,
 * line and area. Reads the built payload and computes all geometry here, so
 * the template only maps arrays to SVG nodes and stays trivial to audit. */

import { Component, useState } from "@odoo/owl";
import { niceScale, seriesColor, formatCompact, formatValue, linePath, smoothPath } from "./svg_util";
import { _t } from "@web/core/l10n/translation";
import { showTooltip, moveTooltip, hideTooltip } from "./tooltip";

const W = 480;
const H = 280;

export class CartesianChart extends Component {
    static template = "eh_board.CartesianChart";
    static props = { payload: Object, meta: { type: Object, optional: true }, onDrill: { type: Function, optional: true } };

    setup() {
        // Series the user clicked off in the legend.
        this.state = useState({ hidden: [] });
    }
    isHidden(i) { return this.state.hidden.includes(i); }
    toggleHidden(i) {
        this.state.hidden = this.isHidden(i)
            ? this.state.hidden.filter((x) => x !== i)
            : [...this.state.hidden, i];
    }
    get legendItems() {
        return this.series.map((s, i) => ({
            label: s.label, index: i, hidden: this.isHidden(i) }));
    }

    get type() {
        return this.props.payload.type || "bar";
    }
    get display() {
        return (this.props.meta && this.props.meta.display) || {};
    }
    get horizontal() {
        return this.type === "hbar";
    }
    get stacked() {
        return this.type === "column" || !!this.display.stacked;
    }
    get showGrid() {
        return this.display.show_grid !== false;
    }
    get showLegend() {
        return this.display.show_legend !== false;
    }
    get smooth() {
        return !!this.display.smooth;
    }
    get isLine() {
        return this.type === "line" || this.type === "area";
    }
    get goalValue() {
        return this.display.goal_value || 0;
    }
    get comboOn() {
        return !!this.display.combo_line && !this.isLine && !this.horizontal;
    }
    get labels() {
        return this.props.payload.labels || [];
    }
    get series() {
        return this.props.payload.series || [];
    }

    get pad() {
        // Horizontal bars hold long category NAMES in the left gutter and value
        // labels past the right end, so both sides need more room than a vertical
        // chart where the left gutter only holds short axis numbers.
        // A combo line rides a secondary axis on the right, so widen that gutter.
        const rightExtra = this.hasComboLines ? 30 : 0;
        return this.horizontal
            ? { top: 16, right: 46 + rightExtra, bottom: 34, left: 112 }
            : { top: 16, right: 16 + rightExtra, bottom: 40, left: 48 };
    }

    get plot() {
        const PAD = this.pad;
        return {
            x: PAD.left, y: PAD.top,
            w: W - PAD.left - PAD.right, h: H - PAD.top - PAD.bottom,
        };
    }

    /** Value-axis extent across all series (stacked sums when stacking). */
    get valueScale() {
        let max = 0, min = 0;
        if (this.stacked) {
            // Track the running cumulative height/depth per category, exactly as
            // the bars stack, so a category mixing positive and negative values
            // keeps its true extent (a net sum would collapse the axis and push
            // the bars outside the plot).
            this.labels.forEach((_, i) => {
                let run = 0;
                this.series.forEach((s, si) => {
                    if (this.isHidden(si) || (this.hasComboLines && s.as_line)) return;
                    run += s.data[i] || 0;
                    max = Math.max(max, run);
                    min = Math.min(min, run);
                });
            });
        } else {
            this.series.forEach((s, si) => {
                // as_line series ride the secondary (line) axis, not this one -
                // but only when the combo actually applies (upright bar chart).
                if (this.isHidden(si) || (this.hasComboLines && s.as_line)) return;
                for (const v of s.data) {
                    max = Math.max(max, v || 0);
                    min = Math.min(min, v || 0);
                }
            });
        }
        // Keep the goal line and the cumulative curve inside the plot.
        if (this.goalValue) max = Math.max(max, this.goalValue);
        if (this.comboOn && this.series[0]) {
            let run = 0;
            for (const v of this.series[0].data) run += v || 0;
            max = Math.max(max, run);
        }
        return niceScale(min, max, 5);
    }

    valueToPx(v) {
        const sc = this.valueScale;
        const ratio = (v - sc.min) / (sc.max - sc.min || 1);
        if (this.horizontal) {
            // RTL: the value axis is on the right and bars grow leftward.
            return this.rtl
                ? this.plot.x + this.plot.w - ratio * this.plot.w
                : this.plot.x + ratio * this.plot.w;
        }
        return this.plot.y + this.plot.h - ratio * this.plot.h;
    }

    get gridLines() {
        const sc = this.valueScale;
        return sc.ticks.map((t) => ({
            value: t,
            label: formatCompact(t),
            pos: this.valueToPx(t),
        }));
    }

    get rtl() {
        const el = typeof document !== "undefined" && document.documentElement;
        return !!(el && (el.dir === "rtl" || document.dir === "rtl"));
    }

    /** One band per category on the category axis. */
    get bands() {
        const n = this.labels.length || 1;
        const size = (this.horizontal ? this.plot.h : this.plot.w) / n;
        // A vertical axis crowds long names; a horizontal axis has a wider gutter.
        const cap = this.horizontal ? 16 : 13;
        // Thin the axis labels when a series is dense (e.g. 18 months of data),
        // so ticks never overlap into an unreadable smear. The full label is
        // always in the tooltip; only the printed tick is skipped.
        const maxTicks = this.horizontal ? 26 : 12;
        const stride = n > maxTicks ? Math.ceil(n / maxTicks) : 1;
        // In an RTL locale the horizontal category axis reads right-to-left; the
        // value axis stays LTR (numbers are latin), so only reverse the columns.
        const mirror = this.rtl && !this.horizontal;
        return this.labels.map((label, i) => {
            const s = String(label == null ? "" : label);
            const idx = mirror ? (n - 1 - i) : i;
            return {
                label,   // full text -> tooltip
                tick: s.length > cap ? s.slice(0, cap - 1) + "…" : s,   // truncated -> axis
                showTick: i % stride === 0,   // thin dense axes to avoid overlap
                index: i,
                start: (this.horizontal ? this.plot.y : this.plot.x) + idx * size,
                size,
            };
        });
    }

    /** Bar rectangles: grouped, or stacked when type === column. */
    get bars() {
        if (this.isLine) return [];
        const out = [];
        const zero = this.valueToPx(0);
        // Visible bar series (non-hidden, not drawn as a line) drive the slot width.
        const visCount = this.series.filter(
            (s, si) => !this.isHidden(si) && !(this.hasComboLines && s.as_line)).length || 1;
        const groupCount = this.stacked ? 1 : visCount;
        this.bands.forEach((band) => {
            const inner = band.size * 0.7;
            const slot = inner / groupCount;
            let stackBase = 0;
            let vi = 0;   // visible index, so hidden series leave no gap
            this.series.forEach((s, si) => {
                // Skip a series only when it is actually drawn as a combo overlay
                // line (upright bar); on horizontal it stays a normal bar.
                if (this.isHidden(si) || (this.hasComboLines && s.as_line)) return;
                const v = s.data[band.index] || 0;
                const color = seriesColor(si);
                const common = { color, value: v, label: band.label,
                    seriesLabel: s.label, index: band.index };
                if (this.horizontal) {
                    const x = Math.min(zero, this.valueToPx(v));
                    const len = Math.abs(this.valueToPx(v) - zero);
                    out.push({
                        ...common, x, y: band.start + band.size * 0.15 + vi * slot,
                        w: len, h: slot * 0.9,
                    });
                } else if (this.stacked) {
                    const top = this.valueToPx(stackBase + v);
                    const bottom = this.valueToPx(stackBase);
                    out.push({
                        ...common, x: band.start + band.size * 0.15, y: Math.min(top, bottom),
                        w: inner, h: Math.abs(bottom - top),
                    });
                    stackBase += v;
                } else {
                    const top = this.valueToPx(v);
                    out.push({
                        ...common, x: band.start + band.size * 0.15 + vi * slot,
                        y: Math.min(zero, top), w: slot * 0.9,
                        h: Math.abs(top - zero),
                    });
                }
                vi++;
            });
        });
        return out;
    }

    /** Line/area paths, one per series. */
    get lines() {
        if (!this.isLine) return [];
        const fill = this.type === "area";
        return this.series.map((s, si) => {
            if (this.isHidden(si)) return null;
            const pts = this.bands.map((band) => ({
                x: band.start + band.size / 2,
                y: this.valueToPx(s.data[band.index] || 0),
            }));
            let area = "";
            if (fill && pts.length) {
                const base = this.valueToPx(0);
                area = linePath(pts)
                    + ` L${pts[pts.length - 1].x.toFixed(2)},${base.toFixed(2)}`
                    + ` L${pts[0].x.toFixed(2)},${base.toFixed(2)} Z`;
            }
            const path = this.smooth ? smoothPath(pts) : linePath(pts);
            return { path, area, color: seriesColor(si), points: pts };
        }).filter(Boolean);
    }

    /** True when any visible series is flagged to draw as a combo line overlay.
     *  Combo lines ride a secondary VERTICAL axis, so they only apply to an
     *  upright bar chart; on a horizontal bar an as_line series stays a bar. */
    get hasComboLines() {
        return !this.isLine && !this.horizontal
            && this.series.some((s, si) => s.as_line && !this.isHidden(si));
    }

    /** Secondary value axis, scaled only over the as_line (combo) series so a
     *  small-magnitude line (e.g. a % rate) still reads over large $ bars. */
    get lineScale() {
        let max = 0, min = 0;
        this.series.forEach((s, si) => {
            if (!s.as_line || this.isHidden(si)) return;
            for (const v of s.data) {
                max = Math.max(max, v || 0);
                min = Math.min(min, v || 0);
            }
        });
        return niceScale(min, max, 5);
    }

    lineToPx(v) {
        const sc = this.lineScale;
        const ratio = (v - sc.min) / (sc.max - sc.min || 1);
        // Combo lines are only drawn on vertical (non-horizontal) charts.
        return this.plot.y + this.plot.h - ratio * this.plot.h;
    }

    /** Combo overlay: as_line series drawn as lines on their own axis. */
    get overlayLines() {
        if (!this.hasComboLines) return [];
        return this.series.map((s, si) => {
            if (!s.as_line || this.isHidden(si)) return null;
            const pts = this.bands.map((band) => ({
                x: band.start + band.size / 2,
                y: this.lineToPx(s.data[band.index] || 0),
            }));
            const path = this.smooth ? smoothPath(pts) : linePath(pts);
            return { path, color: seriesColor(si), points: pts, label: s.label, si };
        }).filter(Boolean);
    }

    /** Right-hand tick labels for the secondary (combo line) axis. */
    get lineTicks() {
        if (!this.hasComboLines) return [];
        return this.lineScale.ticks.map((v) => ({
            pos: this.lineToPx(v), label: formatCompact(v),
        }));
    }

    /** Horizontal goal line at the target value (vertical bar / line charts). */
    get goalLine() {
        if (!this.goalValue || this.horizontal) return null;
        const y = this.valueToPx(this.goalValue);
        return { y, x1: this.plot.x, x2: this.plot.x + this.plot.w,
                 label: formatValue(this.goalValue, this.props.payload.number_format) };
    }

    /** Cumulative running-total overlay of the first series (Pareto). */
    get cumulativePath() {
        if (!this.comboOn || !this.series[0]) return null;
        let run = 0;
        const pts = this.bands.map((band) => {
            run += this.series[0].data[band.index] || 0;
            return { x: band.start + band.size / 2, y: this.valueToPx(run) };
        });
        return { path: linePath(pts), points: pts };
    }

    get viewBox() {
        return `0 0 ${W} ${H}`;
    }

    fmt(v) {
        return formatValue(v, this.props.payload.number_format);
    }

    /** Show value labels only when enabled and the chart is not too dense. */
    get showValues() {
        return this.display.show_values !== false && !this.isLine && this.bars.length <= 16;
    }

    /** Text-label position for a bar's value. */
    valueLabel(bar) {
        if (this.horizontal) {
            return { x: bar.x + bar.w + 4, y: bar.y + bar.h / 2 + 3, anchor: "start" };
        }
        return { x: bar.x + bar.w / 2, y: Math.max(bar.y - 5, 10), anchor: "middle" };
    }

    onBarClick(bar) {
        if (this.props.onDrill) {
            this.props.onDrill({ label: bar.label, index: bar.index });
        }
    }

    // -- tooltip ------------------------------------------------------------
    onBarHover(ev, bar) {
        showTooltip(ev, bar.label, [{ label: bar.seriesLabel || _t("Value"), value: this.fmt(bar.value), color: bar.color }]);
    }
    onBandHover(ev, band) {
        const rows = this.series.map((s, si) => ({
            label: s.label, value: this.fmt(s.data[band.index] || 0), color: seriesColor(si),
        }));
        showTooltip(ev, band.label, rows);
    }
    onMove(ev) {
        moveTooltip(ev);
    }
    onLeave() {
        hideTooltip();
    }
}
