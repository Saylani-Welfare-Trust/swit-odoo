/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * The widget builder: a tabbed (Data / Display / Actions), multi-measure
 * configurator with a live preview. Everything is validated server-side and
 * previewed without persisting until saved. */

import { Component, useState, onWillStart } from "@odoo/owl";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { useService } from "@web/core/utils/hooks";
import { BoardItem } from "./board_item";
import { RichEditor } from "./rich_editor";
import "./registry";

const TYPES = [
    { key: "tile", label: "Tile", group: "kpi", icon: "fa-hashtag" },
    { key: "kpi", label: "KPI", group: "kpi", icon: "fa-bullseye" },
    { key: "gauge", label: "Gauge", group: "kpi", icon: "fa-tachometer" },
    { key: "bar", label: "Bar", group: "chart", icon: "fa-bar-chart" },
    { key: "column", label: "Stacked", group: "chart", icon: "fa-bars" },
    { key: "hbar", label: "Horizontal", group: "chart", icon: "fa-align-left" },
    { key: "line", label: "Line", group: "chart", icon: "fa-line-chart" },
    { key: "area", label: "Area", group: "chart", icon: "fa-area-chart" },
    { key: "pie", label: "Pie", group: "chart", icon: "fa-pie-chart" },
    { key: "doughnut", label: "Doughnut", group: "chart", icon: "fa-circle-o" },
    { key: "radar", label: "Radar", group: "chart", icon: "fa-star-o" },
    { key: "polar", label: "Polar", group: "chart", icon: "fa-life-ring" },
    { key: "radial", label: "Radial", group: "chart", icon: "fa-circle-o-notch" },
    { key: "rose", label: "Rose", group: "chart", icon: "fa-pagelines" },
    { key: "funnel", label: "Funnel", group: "chart", icon: "fa-filter" },
    { key: "pyramid", label: "Pyramid", group: "chart", icon: "fa-sort-amount-asc" },
    { key: "scatter", label: "Scatter", group: "chart", icon: "fa-braille" },
    { key: "map", label: "Map", group: "chart", icon: "fa-globe" },
    { key: "bullet", label: "Bullet", group: "kpi", icon: "fa-tachometer" },
    { key: "heatmap", label: "Heat Map", group: "table", icon: "fa-th" },
    { key: "list", label: "List", group: "table", icon: "fa-table" },
    { key: "pivot", label: "Pivot", group: "table", icon: "fa-th" },
    { key: "decomp", label: "Decomposition", group: "table", icon: "fa-sitemap" },
    { key: "slicer", label: "Slicer", group: "control", icon: "fa-filter" },
    { key: "richtext", label: "Text", group: "content", icon: "fa-font" },
];

const VERBS = [
    { key: "count", label: "Count" },
    { key: "sum", label: "Sum" },
    { key: "avg", label: "Average" },
    { key: "max", label: "Maximum" },
    { key: "min", label: "Minimum" },
    { key: "formula", label: "Calculated" },
];

const ACCENTS = ["mint", "blue", "violet", "amber", "rose", "teal", "indigo"];

export class AddItemDialog extends Component {
    static template = "eh_board.AddItemDialog";
    static components = { BoardItem, DomainSelector, RichEditor };
    static props = {
        dashboardId: Number,
        itemId: { type: [Number, { value: null }], optional: true },
        onSaved: Function,
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.types = TYPES;
        this.verbs = VERBS;
        this.accents = ACCENTS;
        this.state = useState({
            tab: "data",
            title: "",
            item_type: "bar",
            model_id: false,
            model_name: "",
            domain: "[]",
            measureList: [{ verb: "count", field: "", format: "compact", unit: "", formula: "" }],
            dimension: "",
            secondary_dimension: "",
            granularity: "month",
            date_field: "",
            default_date_filter: "none",
            sort_mode: "value_desc",
            sort_field: "",
            sort_order: "desc",
            include_archived: false,
            record_limit_visibility: false,
            record_limit: 0,
            number_format: "compact",
            data_label_type: "value",
            target: 0,
            compare: "none",
            content: "<h2>Heading</h2><p>Your text here.</p>",
            description: "",
            domainOpen: false,
            matchCount: null,
            fieldSearch: "",
            fieldsOpen: false,
            // display
            accent: "mint",
            tile_style: "soft",
            show_legend: true,
            show_values: true,
            show_grid: true,
            semi_circle: false,
            stacked: false,
            smooth: false,
            goal_value: 0,
            combo_line: false,
            // advanced
            cumulative: false,
            fill_gaps: true,
            group_others: false,
            // conditional formatting
            condRules: [],
            // actions
            click_action: "records",
            drill_field: "",
            // meta
            models: [],
            modelSearch: "",
            dimFields: [],
            measureFields: [],
            preview: { meta: null, payload: { error: "Configure a widget to preview it." } },
            previewing: false,
        });
        this._debounce = null;
        this.BoardItem = BoardItem;
        onWillStart(async () => {
            const meta = await this.orm.call(
                "eh.board.dashboard", "get_builder_meta", [[this.props.dashboardId]]);
            this.state.models = meta.models;
            if (this.props.itemId) {
                await this._loadConfig();
            }
            this.refreshPreview();
            this._refreshCount();
        });
    }

    async _loadConfig() {
        const cfg = await this.orm.call(
            "eh.board.dashboard", "get_item_config",
            [[this.props.dashboardId], this.props.itemId]);
        Object.assign(this.state, {
            item_type: cfg.item_type, title: cfg.title, model_id: cfg.model_id,
            model_name: cfg.model_name || "", domain: cfg.domain || "[]",
            measureList: (cfg.measures && cfg.measures.length)
                ? cfg.measures.map((m) => ({
                    verb: m.verb, field: m.field || "",
                    format: m.number_format || "compact", unit: m.unit || "",
                    as_line: !!m.as_line,
                    formula: m.formula || "" }))
                : [{ verb: "count", field: "", format: "compact", unit: "", formula: "" }],
            target: cfg.target || 0,
            compare: cfg.compare || "none",
            dimension: cfg.dimension, secondary_dimension: cfg.secondary_dimension || "",
            granularity: cfg.granularity || "month", date_field: cfg.date_field || "",
            default_date_filter: cfg.default_date_filter || "none",
            accent: cfg.accent || "mint", tile_style: cfg.tile_style || "soft",
            content: cfg.content || "", sort_mode: cfg.sort_mode || "value_desc",
            sort_field: cfg.sort_field || "", sort_order: cfg.sort_order || "desc",
            include_archived: cfg.include_archived || false,
            record_limit_visibility: cfg.record_limit_visibility || false,
            record_limit: cfg.record_limit || 0, number_format: cfg.number_format || "compact",
            data_label_type: cfg.data_label_type || "value",
            show_legend: cfg.show_legend, show_values: cfg.show_values, show_grid: cfg.show_grid,
            semi_circle: cfg.semi_circle, stacked: cfg.stacked, smooth: cfg.smooth,
            goal_value: cfg.goal_value || 0, combo_line: cfg.combo_line,
            cumulative: cfg.cumulative, fill_gaps: cfg.fill_gaps, group_others: cfg.group_others,
            click_action: cfg.click_action || "records", drill_field: cfg.drill_field || "",
            description: cfg.description || "",
            condRules: Array.isArray(cfg.conditional_rules) ? cfg.conditional_rules : [],
        });
        if (cfg.model_id) {
            await this._loadFields(cfg.model_id);
        }
    }

    async _loadFields(modelId) {
        const fields = await this.orm.call(
            "eh.board.dashboard", "get_model_fields",
            [[this.props.dashboardId], modelId]);
        this.state.dimFields = fields.dimensions;
        this.state.measureFields = fields.measures;
    }

    // -- derived ------------------------------------------------------------
    get isEdit() { return !!this.props.itemId; }
    get dialogTitle() { return this.isEdit ? "Edit widget" : "Create a widget"; }
    get needsData() { return !["richtext", "todo"].includes(this.state.item_type); }
    get isSlicer() { return this.state.item_type === "slicer"; }
    // A slicer needs a model + a field but no measure; a chart/table needs both.
    get needsMeasure() { return this.needsData && !this.isSlicer; }
    get needsDimension() {
        return !["kpi", "tile", "gauge", "bullet", "richtext", "todo"].includes(this.state.item_type);
    }
    get isChartType() {
        return !["kpi", "tile", "gauge", "bullet", "slicer", "decomp", "richtext", "todo"].includes(this.state.item_type);
    }
    get isTile() { return ["tile", "kpi"].includes(this.state.item_type); }
    get isPie() { return ["pie", "doughnut"].includes(this.state.item_type); }
    get isBarType() { return ["bar", "column", "hbar"].includes(this.state.item_type); }
    get isLineType() { return ["line", "area"].includes(this.state.item_type); }
    get isRadial() { return ["radar", "polar", "radial", "rose"].includes(this.state.item_type); }
    get isFunnelType() { return ["funnel", "pyramid"].includes(this.state.item_type); }
    get isScatter() { return this.state.item_type === "scatter"; }
    get showConditional() {
        return this.isTile || ["list", "pivot"].includes(this.state.item_type);
    }
    // Every widget can carry an action + a description; only true content blocks
    // (rich text) skip the data-driven tabs.
    get hasActions() { return this.needsData; }
    get hasAdvanced() { return this.isChartType || this.isTile; }
    get dateFields() {
        return this.state.dimFields.filter((d) => d.ttype === "date" || d.ttype === "datetime");
    }

    // -- compact domain: live match count -----------------------------------
    async _refreshCount() {
        if (!this.state.model_name) { this.state.matchCount = null; return; }
        // Parse + count on the server (ast.literal_eval), so a domain value with
        // an apostrophe no longer breaks a client quote-swap and silently counts
        // the whole table. Record rules apply (counted as the current user).
        try {
            this.state.matchCount = await this.orm.call(
                "eh.board.dashboard", "count_domain_matches",
                [this.state.model_name, this.state.domain || "[]",
                 !!this.state.include_archived]);
        } catch (e) {
            this.state.matchCount = null;
        }
    }
    toggleDomain() { this.state.domainOpen = !this.state.domainOpen; }
    onArchivedChange() { this.refreshPreview(); this._refreshCount(); }

    // A plain-English recap of the current config - fills the column floor and
    // doubles as a last read-back before saving.
    get specSummary() {
        const s = this.state;
        if (!this.needsData) return "A text block. Whatever you type renders as-is on the board.";
        if (!s.model_id) return "Pick a model to begin. The preview updates live as you configure.";
        const typeLabel = (TYPES.find((t) => t.key === s.item_type) || {}).label || s.item_type;
        const model = (s.models.find((m) => m.id === s.model_id) || {}).name || s.model_name;
        const measures = s.measureList.map((m) => {
            if (m.verb === "count") return "count of records";
            if (m.verb === "formula") return "a calculated value";
            const v = (VERBS.find((x) => x.key === m.verb) || {}).label || m.verb;
            return v.toLowerCase() + " of " + (m.field || "?");
        }).join(" and ");
        const parts = ["A " + typeLabel.toLowerCase() + " of " + model];
        if (measures) parts.push("showing " + measures);
        if (this.needsDimension && s.dimension) {
            const dim = (s.dimFields.find((d) => d.name === s.dimension) || {}).label || s.dimension;
            parts.push("grouped by " + dim);
            if (s.secondary_dimension) {
                const d2 = (s.dimFields.find((d) => d.name === s.secondary_dimension) || {}).label
                    || s.secondary_dimension;
                parts.push("then " + d2);
            }
        }
        if (parseInt(s.record_limit, 10) > 0) parts.push("top " + s.record_limit);
        if (s.click_action === "records") parts.push("click a mark to open its records");
        else if (s.click_action === "drill") parts.push("click to drill down");
        return parts.join(", ") + ".";
    }

    // -- config changes -----------------------------------------------------
    setTab(tab) { this.state.tab = tab; }
    setType(key) { this.state.item_type = key; this.refreshPreview(); }
    async onModelChange(ev) {
        this.state.model_id = parseInt(ev.target.value, 10) || false;
        this.state.dimension = "";
        this.state.secondary_dimension = "";
        this.state.date_field = "";
        this.state.drill_field = "";
        this.state.domain = "[]";
        const m = this.state.models.find((x) => x.id === this.state.model_id);
        this.state.model_name = m ? m.model : "";
        if (this.state.model_id) {
            await this._loadFields(this.state.model_id);
        }
        this.refreshPreview();
        this._refreshCount();
    }
    onField() { this.refreshPreview(); }
    onContentChange(html) { this.state.content = html; this.refreshPreview(); }
    onDomainChange(domain) {
        // Odoo 17+ hands back a domain string; Odoo 16's DomainSelector hands back
        // a Domain object. Normalise to a string either way.
        this.state.domain = typeof domain === "string"
            ? domain
            : (domain && domain.toString ? domain.toString() : "[]");
        this.refreshPreview();
        this._refreshCount();
    }
    addMeasure() {
        this.state.measureList.push({ verb: "sum", field: "", format: "compact", unit: "", formula: "" });
        this.refreshPreview();
    }
    onNumberFormat() {
        // The Display "Value format" bulk-sets every measure; a per-measure
        // select in the Data tab can still override an individual one.
        for (const m of this.state.measureList) m.format = this.state.number_format;
        this.refreshPreview();
    }
    get isTargetType() {
        return ["kpi", "tile", "gauge", "bullet"].includes(this.state.item_type);
    }
    removeMeasure(i) {
        if (this.state.measureList.length > 1) {
            this.state.measureList.splice(i, 1);
            this.refreshPreview();
        }
    }

    // Models filtered by the search box, matching BOTH the human name and the
    // technical model string (so "sale.report" finds the Sales Analysis model).
    get filteredModels() {
        const q = (this.state.modelSearch || "").toLowerCase().trim();
        if (!q) return this.state.models;
        return this.state.models.filter(
            (m) => (m.name || "").toLowerCase().includes(q)
                || (m.model || "").toLowerCase().includes(q));
    }

    // -- fields quick-pick (Power BI Fields list) ---------------------------
    get filteredDims() {
        const q = (this.state.fieldSearch || "").toLowerCase();
        return this.state.dimFields.filter((d) => !q || (d.label || d.name).toLowerCase().includes(q));
    }
    get filteredMeasures() {
        const q = (this.state.fieldSearch || "").toLowerCase();
        return this.state.measureFields.filter((m) => !q || (m.label || m.name).toLowerCase().includes(q));
    }
    pickDimension(name) {
        // Click a field to fill the next empty grouping well: Group by, then Sub.
        if (!this.state.dimension) this.state.dimension = name;
        else if (!this.state.secondary_dimension) this.state.secondary_dimension = name;
        else this.state.dimension = name;
        this.refreshPreview();
    }
    pickMeasure(name) {
        // Drop a numeric field in as a Sum measure (replace a lone Count).
        const list = this.state.measureList;
        if (list.length === 1 && list[0].verb === "count" && !list[0].field) {
            list[0] = { verb: "sum", field: name, format: "compact", unit: "", formula: "" };
        } else {
            list.push({ verb: "sum", field: name, format: "compact", unit: "", formula: "" });
        }
        this.refreshPreview();
    }

    // drag a field chip from the panel into a well (Group by / Sub / Measures)
    onFieldDrag(ev, name, kind) {
        ev.dataTransfer.setData("text/plain", JSON.stringify({ name, kind }));
        ev.dataTransfer.effectAllowed = "copy";
    }
    allowDrop(ev) { ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; }
    onWellDrop(ev, target) {
        ev.preventDefault();
        let d;
        try { d = JSON.parse(ev.dataTransfer.getData("text/plain")); } catch (e) { return; }
        if (!d || !d.name) return;
        if (target === "measure") this.pickMeasure(d.name);
        else if (target === "secondary") { this.state.secondary_dimension = d.name; this.refreshPreview(); }
        else this.pickDimension(d.name);
    }

    // -- conditional formatting rules ---------------------------------------
    addRule() {
        this.state.condRules.push({ measure: "", op: "gte", v1: 0, v2: 0, color: "#e8590c", style: "text" });
        this.refreshPreview();
    }
    removeRule(i) {
        this.state.condRules.splice(i, 1);
        this.refreshPreview();
    }

    // -- vals ---------------------------------------------------------------
    _vals() {
        const s = this.state;
        const vals = {
            item_type: s.item_type,
            title: s.title || (TYPES.find((t) => t.key === s.item_type) || {}).label || s.item_type,
            accent: s.accent,
            tile_style: s.tile_style,
            show_legend: s.show_legend,
            show_values: s.show_values,
            show_grid: s.show_grid,
            semi_circle: s.semi_circle,
            stacked: s.stacked,
            smooth: s.smooth,
            goal_value: parseFloat(s.goal_value) || 0,
            combo_line: s.combo_line,
            data_label_type: s.data_label_type,
            click_action: s.click_action,
            description: s.description || "",
            conditional_rules: (s.condRules || []).map((r) => ({
                measure: (r.measure === "" || r.measure == null) ? "" : String(r.measure),
                op: r.op, v1: parseFloat(r.v1) || 0, v2: parseFloat(r.v2) || 0,
                color: r.color || "#e8590c", style: r.style || "text",
            })),
        };
        if (this.needsData) {
            vals.model_id = s.model_id;
            vals.domain = s.domain || "[]";
            vals.include_archived = s.include_archived;
            vals.record_limit_visibility = s.record_limit_visibility;
            vals.measures = s.measureList.map((m, i) => {
                const spec = {
                    verb: m.verb,
                    field: (m.verb === "count" || m.verb === "formula") ? null : m.field,
                    number_format: m.format || s.number_format,
                    unit: m.unit || "",
                    formula: m.verb === "formula" ? (m.formula || "0") : "",
                    as_line: !!m.as_line && i > 0,   // combo line only on non-primary
                };
                // Target + comparison apply to the primary measure of a KPI-type.
                if (i === 0 && this.isTargetType) {
                    spec.target = parseFloat(s.target) || 0;
                    spec.compare_mode = s.compare;
                }
                return spec;
            });
            vals.sort_mode = s.sort_mode;
            vals.sort_field = s.sort_mode === "field" ? s.sort_field : "";
            vals.sort_order = s.sort_order;
            vals.record_limit = parseInt(s.record_limit, 10) || 0;
            vals.cumulative = s.cumulative;
            vals.fill_gaps = s.fill_gaps;
            vals.group_others = s.group_others;
            vals.date_field = s.date_field;
            vals.default_date_filter = s.default_date_filter;
            if (s.click_action === "drill") vals.drill_field = s.drill_field;
            if (this.needsDimension && s.dimension) {
                vals.dimension = s.dimension;
                vals.secondary_dimension = s.secondary_dimension;
                const dim = s.dimFields.find((d) => d.name === s.dimension);
                if (dim && (dim.ttype === "date" || dim.ttype === "datetime")) {
                    vals.granularity = s.granularity;
                }
            }
        } else {
            vals.content = s.content;
        }
        return vals;
    }

    // -- preview ------------------------------------------------------------
    refreshPreview() {
        clearTimeout(this._debounce);
        this._debounce = setTimeout(() => this._doPreview(), 250);
    }
    async _doPreview() {
        this.state.previewing = true;
        try {
            this.state.preview = await this.orm.call(
                "eh.board.dashboard", "preview_item",
                [[this.props.dashboardId], this._vals()]);
        } catch (e) {
            this.state.preview = { meta: null, payload: { error: e.message || String(e) } };
        }
        this.state.previewing = false;
    }
    get previewProps() {
        return {
            meta: this.state.preview.meta || {
                type: this.state.item_type, category: "chart",
                component: this.state.item_type, title: this.state.title,
            },
            payload: this.state.preview.payload,
            editMode: false,
            loading: this.state.previewing,
        };
    }

    // -- confirm ------------------------------------------------------------
    get canConfirm() {
        if (!this.needsData) return true;
        if (!this.state.model_id) return false;
        const m = this.state.measureList[0];
        // count needs no field; a formula (calculated) measure uses its formula
        // string, not a field - only value-of-field verbs require a field.
        if (m && m.verb !== "count" && m.verb !== "formula" && !m.field) return false;
        if (m && m.verb === "formula" && !(m.formula || "").trim()) return false;
        if (this.needsDimension && !this.state.dimension) return false;
        return true;
    }
    async confirm() {
        const method = this.isEdit ? "update_item_from_builder" : "add_item";
        const args = this.isEdit
            ? [[this.props.dashboardId], this.props.itemId, this._vals()]
            : [[this.props.dashboardId], this._vals()];
        const res = await this.orm.call("eh.board.dashboard", method, args);
        this.props.onSaved(res, this.isEdit);
        this.props.close();
    }
}
