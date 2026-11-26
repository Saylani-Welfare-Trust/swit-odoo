/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class FavorPopup extends AbstractAwaitablePopup {
    static template = "bn_qurbani.FavorPopup";

    setup() {
        // Initialize services
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        // Set component properties
        this.title = this.props.title || "Donor Details";
        this.placeholder = this.props.placeholder || "Enter Donor Name";

        // Initialize component state
        this.state = useState({
            // the name already given to this order, so it can be corrected
            record_number: this.pos.get_order()?.get_favor() || "",
        });
    }

    /**
     * Update record number from input field
     */
    updateRecordNumber(event) {
        this.state.record_number = event.target.value;
    }

    /**
     * Check if cancel is allowed
     */
    canCancel() {
        return true;
    }

    /**
     * Handle cancel action
     */
    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    /**
     * Put the donor's name on the order (printed on the receipt)
     */
    async confirm() {
        const selectedOrder = this.pos.get_order();
        const name = this.state.record_number.trim();

        if (!name) {
            this.notification.add("Please enter the donor's name", { type: 'info' });
            return;
        }

        selectedOrder.set_favor(name);

        super.confirm();
    }
}