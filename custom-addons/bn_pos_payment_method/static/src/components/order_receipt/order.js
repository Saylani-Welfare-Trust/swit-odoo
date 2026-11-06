/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

// The receipt shows the bank / cheque / card details by the kind of payment
// method of the order (fields of this module).
patch(Order.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        const method = this.paymentlines[0]?.payment_method;
        return {
            ...result,
            is_bank: method?.is_bank,
        };
    },
});
