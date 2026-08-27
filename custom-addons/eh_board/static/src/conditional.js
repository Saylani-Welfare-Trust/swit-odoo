/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * Conditional formatting: evaluate a widget's colour rules against a numeric
 * value and return how to paint it. First matching rule wins (Power BI style).
 * Rule shape: { measure, op, v1, v2, color, style } where
 *   op    = gt | gte | lt | lte | eq | ne | between
 *   style = text | fill | bar  (colour the number, the cell, or a data bar) */

export function matchRule(rules, value, measureIndex) {
    if (!Array.isArray(rules) || !rules.length) return null;
    const v = typeof value === "number" ? value : parseFloat(value);
    if (v == null || isNaN(v)) return null;
    for (const r of rules) {
        // r.measure "" / undefined = all measures; otherwise it targets one
        // measure by its 0-based index in the widget's measure list.
        if (r.measure !== undefined && r.measure !== "" && r.measure !== null
            && measureIndex !== undefined && Number(r.measure) !== Number(measureIndex)) continue;
        const v1 = parseFloat(r.v1), v2 = parseFloat(r.v2);
        // Float-tolerant equality: a summed measure is rarely bit-exact, so
        // eq/ne compare within a small relative epsilon instead of ===.
        const eq = Math.abs(v - v1) <= 1e-9 + 1e-9 * Math.max(Math.abs(v), Math.abs(v1));
        let hit = false;
        switch (r.op) {
            case "gt": hit = v > v1; break;
            case "gte": hit = v >= v1; break;
            case "lt": hit = v < v1; break;
            case "lte": hit = v <= v1; break;
            case "eq": hit = eq; break;
            case "ne": hit = !eq; break;
            case "between": hit = v >= v1 && v <= v2; break;
            default: hit = false;
        }
        if (hit) return { color: r.color || "#1baf7a", style: r.style || "text" };
    }
    return null;
}

/** A CSS style string for one value given the rules (text/fill), or "". */
export function condStyle(rules, value, measureKey) {
    const m = matchRule(rules, value, measureKey);
    if (!m) return "";
    if (m.style === "fill") {
        return `background:${m.color};color:${textOn(m.color)};`;
    }
    return `color:${m.color};font-weight:700;`;
}

/** Pick readable text (black/white) for a fill colour. Handles #rgb, #rrggbb,
 *  rgb()/rgba(), and any named/var() colour (default to dark on unknown). */
export function textOn(color) {
    const c = (color || "").trim();
    let r, g, b;
    let m = /^#([0-9a-f]{3})$/i.exec(c);
    if (m) {
        r = parseInt(m[1][0] + m[1][0], 16);
        g = parseInt(m[1][1] + m[1][1], 16);
        b = parseInt(m[1][2] + m[1][2], 16);
    } else if ((m = /^#([0-9a-f]{6})$/i.exec(c))) {
        r = parseInt(m[1].slice(0, 2), 16);
        g = parseInt(m[1].slice(2, 4), 16);
        b = parseInt(m[1].slice(4, 6), 16);
    } else if ((m = /rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(c))) {
        r = +m[1]; g = +m[2]; b = +m[3];
    } else {
        return "#111";   // named / var() / unknown -> assume light fill
    }
    return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? "#111" : "#fff";
}
