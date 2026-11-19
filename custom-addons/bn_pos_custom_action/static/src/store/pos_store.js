/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    // The server gives each saved order its receipt number (pos_order_seq):
    // put it on the order before its receipt is printed.
    async _save_to_server(orders, options) {
        const result = await super._save_to_server(...arguments);
        for (const res of result || []) {
            if (!res.pos_order_seq) {
                continue;
            }
            const order = this.orders.find((o) => o.name === res.pos_reference);
            if (order) {
                order.set_pos_order_seq(res.pos_order_seq);
            }
        }
        return result;
    },
});
