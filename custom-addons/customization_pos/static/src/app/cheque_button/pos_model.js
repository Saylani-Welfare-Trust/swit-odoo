/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {
    set_order_return_reason(cheque_number) {
        this.cheque_number = cheque_number;
    },

    get_order_return_reason() {
        return this.cheque_number;
    },

    export_as_JSON() {
        const json = super.export_as_JSON();
        json.cheque_number = this.get_order_return_reason() || null;
        return json;
    },

    export_for_printing() {
        const order = super.export_for_printing();
        const new_val = {
            cheque_number: this.get_order_return_reason() || false,
        };
        Object.assign(order, new_val);
        return order;
    },
});
