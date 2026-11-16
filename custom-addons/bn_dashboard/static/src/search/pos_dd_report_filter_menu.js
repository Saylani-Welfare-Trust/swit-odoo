/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";

/**
 * POS & Direct Deposits report: the server adds one filter per city
 * (name "pdd_city_<id>") and per branch ("pdd_branch_<id>") to the search
 * view. Here they are folded into a "City" and a "Branch" expandable entry in
 * the Filters list, rendered exactly like Odoo's own "Date" filter.
 */
const GROUPS = {
    city: () => _t("City"),
    branch: () => _t("Branch"),
};
const NAME_RE = /^pdd_(city|branch)_\d+$/;

patch(SearchBarMenu.prototype, {
    get filterItems() {
        const items = super.filterItems;
        if (this.env.searchModel.resModel !== "pos.dd.report") {
            return items;
        }
        const result = [];
        const folded = {};
        for (const item of items) {
            const match = item.name && item.name.match(NAME_RE);
            if (!match) {
                result.push(item);
                continue;
            }
            const key = match[1];
            if (!folded[key]) {
                folded[key] = {
                    id: `pdd_${key}`,
                    description: GROUPS[key](),
                    groupNumber: item.groupNumber,
                    isActive: false,
                    options: [],
                };
                result.push(folded[key]);
            }
            folded[key].options.push({
                id: item.id,
                description: item.description,
                groupNumber: item.groupNumber,
                isActive: item.isActive,
            });
            folded[key].isActive = folded[key].isActive || item.isActive;
        }
        return result;
    },

    onFilterSelected({ itemId, optionId }) {
        if (typeof itemId === "string" && itemId.startsWith("pdd_")) {
            // optionId is the real search item of the chosen city / branch
            this.env.searchModel.toggleSearchItem(optionId);
            return;
        }
        return super.onFilterSelected(...arguments);
    },
});
