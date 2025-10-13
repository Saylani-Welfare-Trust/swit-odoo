/** @odoo-module */

import { useAutofocus, useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

// NOTE: These are constants so that they are only instantiated once
// and they can be used efficiently by the OrderManagementControlPanel.
const VALID_SEARCH_TAGS = new Set(["date", "customer", "client", "name", "order"]);
const FIELD_MAP = {
    date: "create_date",
    customer: "partner_id.complete_name",
    client: "partner_id.complete_name",
    name: "name",
    order: "name",
};
const SEARCH_FIELDS = ["name", "partner_id.complete_name", "create_date"];

/**
 * @emits search
 */
export class RecurringOrderManagementControlPanel extends Component {
    static template = "pos_enhancement.RecurringOrderManagementControlPanel";

    setup() {
        this.pos = usePos();
        this.ui = useState(useService("ui"));
        this.recurringOrderFetcher = useService("recurring_order_fetcher");
        useAutofocus();

        const currentPartner = this.pos.get_order().get_partner();
        if (currentPartner) {
            this.pos.orderManagement.searchString = currentPartner.name;
        }
        this.recurringOrderFetcher.setSearchDomain(this._computeDomain());
    }
    onInputKeydown(event) {
        if (event.key === "Enter") {
            this.props.onSearch(this._computeDomain());
        }
    }
    get showPageControls() {
        return this.recurringOrderFetcher.lastPage > 1;
    }
    get pageNumber() {
        const currentPage = this.recurringOrderFetcher.currentPage;
        const lastPage = this.recurringOrderFetcher.lastPage;
        return isNaN(lastPage) ? "" : `(${currentPage}/${lastPage})`;
    }
    get validSearchTags() {
        return VALID_SEARCH_TAGS;
    }
    get fieldMap() {
        return FIELD_MAP;
    }
    get searchFields() {
        return SEARCH_FIELDS;
    }

    _computeDomain() {
        let domain = [
            ['order_type','=','recurring'],
        ];
        const input = this.pos.orderManagement.searchString.trim();
        if (!input) {
            return domain;
        }

        const searchConditions = this.pos.orderManagement.searchString.split(/[,&]\s*/);
        if (searchConditions.length === 1) {
            const cond = searchConditions[0].split(/:\s*/);
            if (cond.length === 1) {
                domain = domain.concat(Array(this.searchFields.length - 1).fill("|"));
                domain = domain.concat(
                    this.searchFields.map((field) => [field, "ilike", `%${cond[0]}%`])
                );
                return domain;
            }
        }

        for (const cond of searchConditions) {
            const [tag, value] = cond.split(/:\s*/);
            if (!this.validSearchTags.has(tag)) {
                continue;
            }
            domain.push([this.fieldMap[tag], "ilike", `%${value}%`]);
        }
        return domain;
    }
    clearSearch() {
        this.pos.orderManagement.searchString = "";
        this.onInputKeydown({ key: "Enter" });
    }
}
