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
            record_number: "",
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
     * Main confirm method - handles medical equipment record processing
     */
    async confirm() {
        const selectedOrder = this.pos.get_order();

        if (!this.state.record_number) {
            this.notification.add(
                "Please Enter a Number",
                { type: 'info' }
            );
        }
        
        selectedOrder.set_favor(this.state.record_number);

        super.confirm();
    }
}