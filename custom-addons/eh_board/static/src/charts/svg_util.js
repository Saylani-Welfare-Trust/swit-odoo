/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Pure helpers for the original SVG charts: linear scales, "nice" axis ticks,
 * number formatting and the themed series palette. No third-party charting
 * library - the same approach shipped in the Gantt planner. */

export function niceNum(range, round) {
    const exponent = Math.floor(Math.log10(range || 1));
    const fraction = (range || 1) / Math.pow(10, exponent);
    let niceFraction;
    if (round) {
        if (fraction < 1.5) niceFraction = 1;
        else if (fraction < 3) niceFraction = 2;
        else if (fraction < 7) niceFraction = 5;
        else niceFraction = 10;
    } else if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
    return niceFraction * Math.pow(10, exponent);
}

/** Return {min, max, step, ticks[]} for a value axis that includes 0. */
export function niceScale(minValue, maxValue, maxTicks = 5) {
    let lo = Math.min(0, minValue);
    let hi = Math.max(0, maxValue);
    if (lo === hi) hi = lo + 1;
    const range = niceNum(hi - lo, false);
    const step = niceNum(range / (maxTicks - 1), true);
    const niceMin = Math.floor(lo / step) * step;
    const niceMax = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let v = niceMin; v <= niceMax + step / 2; v += step) {
        ticks.push(Math.round(v * 1e6) / 1e6);
    }
    return { min: niceMin, max: niceMax, step, ticks };
}

/** Compact human number: 1234567 -> "1.2M". */
export function formatCompact(value, digits = 1) {
    const n = Number(value) || 0;
    const abs = Math.abs(n);
    const sign = n < 0 ? "-" : "";
    if (abs >= 1e9) return sign + (abs / 1e9).toFixed(digits).replace(/\.0$/, "") + "B";
    if (abs >= 1e6) return sign + (abs / 1e6).toFixed(digits).replace(/\.0$/, "") + "M";
    if (abs >= 1e3) return sign + (abs / 1e3).toFixed(digits).replace(/\.0$/, "") + "K";
    if (Number.isInteger(n)) return String(n);
    return n.toFixed(digits);
}

export function formatValue(value, format = "compact") {
    const n = Number(value) || 0;
    switch (format) {
        case "plain":
            return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
        case "thousands":
            return (n / 1e3).toLocaleString(undefined, { maximumFractionDigits: 1 }) + "K";
        case "millions":
            return (n / 1e6).toLocaleString(undefined, { maximumFractionDigits: 1 }) + "M";
        default:
            return formatCompact(n);
    }
}

/** The N-th series colour. The first eight come from themed CSS custom
 *  properties; beyond that, generate distinct hues by the golden angle so a 9th
 *  category never reuses the 1st colour (two marks the same colour misreads the
 *  chart). */
export function seriesColor(index) {
    const palette = [
        "--eh-board-series-1", "--eh-board-series-2", "--eh-board-series-3",
        "--eh-board-series-4", "--eh-board-series-5", "--eh-board-series-6",
        "--eh-board-series-7", "--eh-board-series-8",
    ];
    if (index < palette.length) return `var(${palette[index]})`;
    // Golden-angle spacing keeps successive extra hues maximally distinct.
    const hue = Math.round((index * 137.508) % 360);
    return `hsl(${hue}, 62%, 52%)`;
}

/** SVG path "d" for a polyline through [{x, y}] points. */
export function linePath(points) {
    if (!points.length) return "";
    return points
        .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
        .join(" ");
}

/** Smoothed path through points (Catmull-Rom -> cubic bezier). */
export function smoothPath(points) {
    if (points.length < 3) return linePath(points);
    let d = `M${points[0].x.toFixed(2)},${points[0].y.toFixed(2)}`;
    for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[i - 1] || points[i];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[i + 2] || p2;
        const c1x = p1.x + (p2.x - p0.x) / 6;
        const c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6;
        const c2y = p2.y - (p3.y - p1.y) / 6;
        d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} `
            + `${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
    }
    return d;
}

/** SVG arc path for a pie/doughnut slice between two angles (radians). */
export function arcPath(cx, cy, rOuter, rInner, a0, a1) {
    const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    // A single-category pie / polar / rose spans a full 360 deg: the start and
    // end points coincide, so a lone A-command draws NOTHING (the slice would
    // paint blank). Emit a full circle / annulus as two half-arcs instead.
    if (a1 - a0 >= 2 * Math.PI - 1e-6) {
        const m = a0 + Math.PI;
        const [x0, y0] = p(rOuter, a0);
        const [xm, ym] = p(rOuter, m);
        if (rInner <= 0) {
            return `M${x0},${y0} A${rOuter},${rOuter} 0 1 1 ${xm},${ym} `
                + `A${rOuter},${rOuter} 0 1 1 ${x0},${y0} Z`;
        }
        // Donut: outer ring clockwise, inner ring counter-clockwise punches the
        // hole (non-zero winding).
        const [ix0, iy0] = p(rInner, a0);
        const [ixm, iym] = p(rInner, m);
        return `M${x0},${y0} A${rOuter},${rOuter} 0 1 1 ${xm},${ym} `
            + `A${rOuter},${rOuter} 0 1 1 ${x0},${y0} Z `
            + `M${ix0},${iy0} A${rInner},${rInner} 0 1 0 ${ixm},${iym} `
            + `A${rInner},${rInner} 0 1 0 ${ix0},${iy0} Z`;
    }
    const [x0, y0] = p(rOuter, a0);
    const [x1, y1] = p(rOuter, a1);
    const large = a1 - a0 > Math.PI ? 1 : 0;
    if (rInner <= 0) {
        return `M${cx},${cy} L${x0},${y0} A${rOuter},${rOuter} 0 ${large} 1 ${x1},${y1} Z`;
    }
    const [ix1, iy1] = p(rInner, a1);
    const [ix0, iy0] = p(rInner, a0);
    return `M${x0},${y0} A${rOuter},${rOuter} 0 ${large} 1 ${x1},${y1} `
        + `L${ix1},${iy1} A${rInner},${rInner} 0 ${large} 0 ${ix0},${iy0} Z`;
}
