/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { sprintf } from "@web/core/utils/strings";
import { parseFloat } from "@web/views/fields/parsers";
import { floatIsZero } from "@web/core/utils/numbers";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { ControlButtonsMixin } from "@point_of_sale/app/utils/control_buttons_mixin";
import { Orderline } from "@point_of_sale/app/store/models";

import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { RecurringOrderList } from "../recurring_order_list/recurrring_order_list";
import { RecurringOrderManagementControlPanel } from "../recurring_order_management_controlpanel/recurring_order_management_controlpanel";
import { Component, onMounted, useRef } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

/**
 * ID getter to take into account falsy many2one value.
 * @param {[id: number, display_name: string] | false} fieldVal many2one field value
 * @returns {number | false}
 */
function getId(fieldVal) {
    return fieldVal && fieldVal[0];
}

export class RecurringOrdersScreen extends Component {
    static storeOnOrder = false;
    static components = { RecurringOrderList, RecurringOrderManagementControlPanel };
    static template = "pos_enhancement.RecurringOrderScreen";

    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.root = useRef("root");
        this.numberBuffer = useService("number_buffer");
        this.recurringOrderFetcher = useService("recurring_order_fetcher");
        this.notification = useService("pos_notification");
        useBus(this.recurringOrderFetcher, "update", this.render);

        onMounted(this.onMounted);
    }
    onMounted() {
        const flexContainer = this.root.el.querySelector(".flex-container");
        const cpEl = this.root.el.querySelector(".control-panel");
        const headerEl = this.root.el.querySelector(".header-row");
        const val = Math.trunc(
            (flexContainer.offsetHeight - cpEl.offsetHeight - headerEl.offsetHeight) /
                headerEl.offsetHeight
        );
        this.recurringOrderFetcher.setNPerPage(val);
        this.recurringOrderFetcher.fetch();
    }

    get orders() {
        return this.recurringOrderFetcher.get();
    }
    onNextPage() {
        this.recurringOrderFetcher.nextPage();
    }
    onPrevPage() {
        this.recurringOrderFetcher.prevPage();
    }
    onSearch(domain) {
        this.recurringOrderFetcher.setSearchDomain(domain);
        this.recurringOrderFetcher.setPage(1);
        this.recurringOrderFetcher.fetch();
    }

}

registry.category("pos_screens").add("RecurringOrderScreen", RecurringOrdersScreen);
