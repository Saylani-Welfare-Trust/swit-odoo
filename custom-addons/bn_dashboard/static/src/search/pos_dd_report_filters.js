/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { Dialog } from "@web/core/dialog/dialog";
import { Domain } from "@web/core/domain";
import { formatDate, serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";

const { DateTime } = luxon;

const REPORT_MODEL = "pos.dd.report";

/**
 * POS & Direct Deposits report: "Date Range", "City" and "Branch" entries in
 * the Filters list. Clicking one opens a popup; applying it adds one facet
 * (removable from the search bar). Re-applying replaces that facet.
 */

// ---------------------------------------------------------------------------
// Facet bookkeeping (kept on the search model)
// ---------------------------------------------------------------------------
function isGroupActive(searchModel, groupId) {
    return searchModel.query.some(
        (q) => searchModel.searchItems[q.searchItemId]?.groupId === groupId
    );
}

/** Current applied value for `key` ("date" | "city" | "branch"), or null. */
function getApplied(searchModel, key) {
    const entry = searchModel.posDdFilters?.[key];
    if (entry && isGroupActive(searchModel, entry.groupId)) {
        return entry.value;
    }
    return null;
}

/** Replace the facet for `key` with `part` ({ description, domain, value }), or remove it. */
function setApplied(searchModel, key, part) {
    if (!searchModel.posDdFilters) {
        searchModel.posDdFilters = {};
    }
    const previous = searchModel.posDdFilters[key];
    searchModel.blockNotification = true;
    try {
        if (previous && isGroupActive(searchModel, previous.groupId)) {
            searchModel.deactivateGroup(previous.groupId);
        }
        delete searchModel.posDdFilters[key];
        if (part) {
            const groupId = searchModel.nextGroupId;
            searchModel.createNewFilters([
                {
                    description: part.description,
                    domain: new Domain(part.domain).toString(),
                    invisible: "True", // shown as a facet; the list entry opens the popup
                },
            ]);
            searchModel.posDdFilters[key] = { groupId, value: part.value };
        }
    } finally {
        searchModel.blockNotification = false;
    }
    searchModel._notify();
}

function summarize(names) {
    const shown = names.slice(0, 3).join(", ");
    return names.length > 3 ? _t("%s +%s more", shown, names.length - 3) : shown;
}

// ---------------------------------------------------------------------------
// Date range popup
// ---------------------------------------------------------------------------
export class PosDdDateRangeDialog extends Component {
    static template = "bn_dashboard.PosDdDateRangeDialog";
    static components = { Dialog, DateTimePicker };
    static props = {
        close: Function,
        value: { type: [Object, { value: null }], optional: true },
        onApply: Function,
    };

    setup() {
        const value = this.props.value || {};
        this.state = useState({ from: value.from || null, to: value.to || null });
        const today = DateTime.local().startOf("day");
        this.presets = [
            { label: _t("This Month"), from: today.startOf("month"), to: today.endOf("month") },
            {
                label: _t("Last Month"),
                from: today.minus({ months: 1 }).startOf("month"),
                to: today.minus({ months: 1 }).endOf("month"),
            },
            {
                label: _t("Last 2 Months"),
                from: today.minus({ months: 1 }).startOf("month"),
                to: today.endOf("month"),
            },
            { label: _t("This Year"), from: today.startOf("year"), to: today.endOf("year") },
        ].map((p) => ({ ...p, from: p.from.startOf("day"), to: p.to.startOf("day") }));
    }

    get dialogTitle() {
        return _t("Filter by Date Range");
    }

    get pickerValue() {
        return [this.state.from || null, this.state.to || null];
    }

    get focusedDateIndex() {
        return this.state.from && !this.state.to ? 1 : 0;
    }

    get rangeLabel() {
        const { from, to } = this.state;
        if (!from) {
            return _t("Click a start date, then an end date.");
        }
        if (!to) {
            return _t("From %s — now click the end date.", formatDate(from));
        }
        return _t("From %s to %s", formatDate(from), formatDate(to));
    }

    onSelect(value) {
        const [start, end] = Array.isArray(value) ? value : [value, null];
        const { from, to } = this.state;
        if (from && to) {
            // A full range was already chosen: the click starts a new range.
            const startChanged = +start !== +from;
            const endChanged = +end !== +to;
            const clicked = startChanged ? start : endChanged ? end : start;
            this.state.from = clicked;
            this.state.to = null;
        } else {
            this.state.from = start || null;
            this.state.to = end || null;
        }
    }

    usePreset(preset) {
        this.state.from = preset.from;
        this.state.to = preset.to;
    }

    apply() {
        const from = this.state.from;
        const to = this.state.to || this.state.from; // single click = that one day
        if (!from) {
            return;
        }
        const label = +from === +to
            ? formatDate(from)
            : `${formatDate(from)} – ${formatDate(to)}`;
        this.props.onApply({
            description: _t("Date: %s", label),
            domain: [
                ["date_day", ">=", serializeDate(from)],
                ["date_day", "<=", serializeDate(to)],
            ],
            value: { from, to },
        });
        this.props.close();
    }

    clear() {
        this.props.onApply(null);
        this.props.close();
    }
}

// ---------------------------------------------------------------------------
// City / Branch popup
// ---------------------------------------------------------------------------
export class PosDdLocationDialog extends Component {
    static template = "bn_dashboard.PosDdLocationDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        kind: { type: String, validate: (k) => ["city", "branch"].includes(k) },
        selectedIds: { type: Array, optional: true },
        cityIds: { type: Array, optional: true }, // branch popup: restrict to these cities
        onApply: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            search: "",
            selected: new Set(this.props.selectedIds || []),
            options: [],
            loading: true,
        });
        onWillStart(async () => {
            const data = await this.orm.call(REPORT_MODEL, "get_location_filter_options", []);
            let options;
            if (this.props.kind === "city") {
                options = data.cities;
            } else {
                options = data.branches;
                if (this.props.cityIds?.length) {
                    options = options.filter((b) => this.props.cityIds.includes(b.city_id));
                }
            }
            this.state.options = options;
            this.state.loading = false;
        });
    }

    get title() {
        return this.props.kind === "city" ? _t("Filter by City") : _t("Filter by Branch");
    }

    get cityNote() {
        if (this.props.kind !== "branch" || !this.props.cityIds?.length) {
            return "";
        }
        return _t("Showing branches of the selected cities only.");
    }

    get visibleOptions() {
        const term = this.state.search.trim().toLowerCase();
        if (!term) {
            return this.state.options;
        }
        return this.state.options.filter(
            (o) =>
                o.name.toLowerCase().includes(term) ||
                (o.city_name || "").toLowerCase().includes(term)
        );
    }

    get allVisibleSelected() {
        const visible = this.visibleOptions;
        return visible.length > 0 && visible.every((o) => this.state.selected.has(o.id));
    }

    toggle(id) {
        if (this.state.selected.has(id)) {
            this.state.selected.delete(id);
        } else {
            this.state.selected.add(id);
        }
    }

    toggleAllVisible() {
        const select = !this.allVisibleSelected;
        for (const o of this.visibleOptions) {
            if (select) {
                this.state.selected.add(o.id);
            } else {
                this.state.selected.delete(o.id);
            }
        }
    }

    apply() {
        const chosen = this.state.options.filter((o) => this.state.selected.has(o.id));
        if (!chosen.length) {
            this.clear();
            return;
        }
        const ids = chosen.map((o) => o.id);
        const isCity = this.props.kind === "city";
        this.props.onApply({
            description: isCity
                ? _t("City: %s", summarize(chosen.map((o) => o.name)))
                : _t("Branch: %s", summarize(chosen.map((o) => o.name))),
            domain: [[isCity ? "city_id" : "analytic_account_id", "in", ids]],
            value: { ids },
        });
        this.props.close();
    }

    clear() {
        this.props.onApply(null);
        this.props.close();
    }
}

// ---------------------------------------------------------------------------
// Filters list entries
// ---------------------------------------------------------------------------
const ENTRIES = [
    { id: "pdd_date", key: "date", label: () => _t("Date Range") },
    { id: "pdd_city", key: "city", label: () => _t("City") },
    { id: "pdd_branch", key: "branch", label: () => _t("Branch") },
];

patch(SearchBarMenu.prototype, {
    get filterItems() {
        const items = super.filterItems;
        const searchModel = this.env.searchModel;
        if (searchModel.resModel !== REPORT_MODEL) {
            return items;
        }
        return [
            ...items,
            ...ENTRIES.map((entry) => ({
                id: entry.id,
                description: entry.label(),
                groupNumber: "pdd_popup_filters",
                isActive: Boolean(getApplied(searchModel, entry.key)),
            })),
        ];
    },

    onFilterSelected({ itemId, optionId }) {
        const entry = ENTRIES.find((e) => e.id === itemId);
        if (!entry) {
            return super.onFilterSelected(...arguments);
        }
        const searchModel = this.env.searchModel;
        const onApply = (part) => setApplied(searchModel, entry.key, part);
        if (entry.key === "date") {
            this.dialogService.add(PosDdDateRangeDialog, {
                value: getApplied(searchModel, "date"),
                onApply,
            });
        } else {
            const applied = getApplied(searchModel, entry.key);
            const cities = getApplied(searchModel, "city");
            this.dialogService.add(PosDdLocationDialog, {
                kind: entry.key,
                selectedIds: applied ? applied.ids : [],
                cityIds: entry.key === "branch" && cities ? cities.ids : [],
                onApply,
            });
        }
    },
});
