/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { Domain } from "@web/core/domain";
import { formatDate, serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";

const REPORT_MODEL = "pos.dd.report";

/**
 * "Date Range / City / Branch" box shown inside the Filters dropdown of the
 * POS & Direct Deposits report. Each part is added as its own facet, so the
 * parts AND together and can be removed one by one from the search bar.
 * Re-applying a part replaces the facet it created before.
 */
export class PosDdReportFilterBox extends Component {
    static template = "bn_dashboard.PosDdReportFilterBox";
    static components = { DateTimeInput };
    static props = {};

    setup() {
        this.orm = useService("orm");
        const sm = this.env.searchModel;
        // Draft and created-group ids live on the search model so they survive
        // the dropdown being closed and reopened.
        if (!sm.posDdDraft) {
            sm.posDdDraft = { dateFrom: false, dateTo: false, cityId: false, branchId: false };
        }
        if (!sm.posDdGroups) {
            sm.posDdGroups = {};
        }
        this.draft = useState(sm.posDdDraft);
        this.options = useState({ cities: [], branches: [] });
        this.placeholders = { from: _t("From"), to: _t("To") };
        this._syncDraftWithFacets();

        onWillStart(async () => {
            await Promise.all([this.loadCities(), this.loadBranches()]);
        });
    }

    // ------------------------------------------------------------------
    // Options (only locations that actually have rows the user may see)
    // ------------------------------------------------------------------
    async _loadGroups(field, domain) {
        const groups = await this.orm.readGroup(REPORT_MODEL, domain, [field], [field]);
        return groups
            .filter((g) => g[field])
            .map((g) => ({ id: g[field][0], name: g[field][1] }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }

    async loadCities() {
        this.options.cities = await this._loadGroups("city_id", []);
    }

    async loadBranches() {
        const domain = this.draft.cityId ? [["city_id", "=", this.draft.cityId]] : [];
        this.options.branches = await this._loadGroups("analytic_account_id", domain);
    }

    // ------------------------------------------------------------------
    // Handlers
    // ------------------------------------------------------------------
    onDateFromChange(value) {
        this.draft.dateFrom = value || false;
    }

    onDateToChange(value) {
        this.draft.dateTo = value || false;
    }

    async onCityChange(ev) {
        this.draft.cityId = parseInt(ev.target.value) || false;
        this.draft.branchId = false;
        await this.loadBranches();
    }

    onBranchChange(ev) {
        this.draft.branchId = parseInt(ev.target.value) || false;
    }

    get canApply() {
        const { dateFrom, dateTo, cityId, branchId } = this.draft;
        return Boolean(dateFrom || dateTo || cityId || branchId);
    }

    apply() {
        const { dateFrom, dateTo, cityId, branchId } = this.draft;
        const parts = {
            date: null,
            city: null,
            branch: null,
        };

        if (dateFrom || dateTo) {
            const domain = [];
            if (dateFrom) {
                domain.push(["date_day", ">=", serializeDate(dateFrom)]);
            }
            if (dateTo) {
                domain.push(["date_day", "<=", serializeDate(dateTo)]);
            }
            let description;
            if (dateFrom && dateTo) {
                description = _t("Date: %s – %s", formatDate(dateFrom), formatDate(dateTo));
            } else if (dateFrom) {
                description = _t("Date: from %s", formatDate(dateFrom));
            } else {
                description = _t("Date: until %s", formatDate(dateTo));
            }
            parts.date = { description, domain };
        }
        if (cityId) {
            const name = this.options.cities.find((c) => c.id === cityId)?.name || cityId;
            parts.city = {
                description: _t("City: %s", name),
                domain: [["city_id", "=", cityId]],
            };
        }
        if (branchId) {
            const name = this.options.branches.find((b) => b.id === branchId)?.name || branchId;
            parts.branch = {
                description: _t("Branch: %s", name),
                domain: [["analytic_account_id", "=", branchId]],
            };
        }

        const sm = this.env.searchModel;
        sm.blockNotification = true;
        try {
            for (const [key, part] of Object.entries(parts)) {
                // Clearing a part in the box removes its facet; setting it replaces the facet.
                if (sm.posDdGroups[key] !== undefined) {
                    sm.deactivateGroup(sm.posDdGroups[key]);
                    delete sm.posDdGroups[key];
                }
                if (part) {
                    sm.posDdGroups[key] = sm.nextGroupId;
                    sm.createNewFilters([
                        {
                            description: part.description,
                            domain: new Domain(part.domain).toString(),
                            invisible: "True", // facet only; the box is the UI for it
                        },
                    ]);
                }
            }
        } finally {
            sm.blockNotification = false;
        }
        sm._notify();
    }

    clear() {
        Object.assign(this.draft, { dateFrom: false, dateTo: false, cityId: false, branchId: false });
        this.loadBranches();
        this.apply();
    }

    // ------------------------------------------------------------------
    // If a facet was removed from the search bar, drop it from the draft too.
    // ------------------------------------------------------------------
    _syncDraftWithFacets() {
        const sm = this.env.searchModel;
        const activeGroupIds = new Set(
            sm.query.map((q) => sm.searchItems[q.searchItemId]?.groupId)
        );
        const resets = {
            date: { dateFrom: false, dateTo: false },
            city: { cityId: false },
            branch: { branchId: false },
        };
        for (const [key, groupId] of Object.entries(sm.posDdGroups)) {
            if (!activeGroupIds.has(groupId)) {
                Object.assign(this.draft, resets[key]);
                delete sm.posDdGroups[key];
            }
        }
    }
}

SearchBarMenu.components = { ...SearchBarMenu.components, PosDdReportFilterBox };
