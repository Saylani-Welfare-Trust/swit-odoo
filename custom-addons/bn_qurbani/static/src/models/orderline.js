/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    hasQurbani(order) {
        // Only lines booked through the Qurbani Schedule popup; lines loaded from a DHS must still merge
        return order.get_orderlines().some(line => line.qurbani_schedule && this.pos.isQurbaniProduct(line.product));
    },

    set_quantity(quantity, keep_price) {
        const order = this.order;

        if (order && this.hasQurbani(order)) {
            // 🔥 Allow only decreasing quantity (Backspace behavior)
            if (quantity > this.quantity) {
                return true; // ❌ block increase/edit
            }
        }

        return super.set_quantity(quantity, keep_price);
    },
});