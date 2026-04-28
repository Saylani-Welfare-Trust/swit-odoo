/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

function hasQurbani(order) {
    return order.get_orderlines().some(line => {
        const product = line.product;
        return (
            product.is_livestock &&
            product.detailed_type === "product" &&
            product.categ?.name?.toLowerCase().includes("qurbani")
        );
    });
}

patch(Orderline.prototype, {
    set_quantity(quantity, keep_price) {
        const order = this.order;

        if (order && hasQurbani(order)) {
            // 🔥 Allow only decreasing quantity (Backspace behavior)
            if (quantity < this.quantity) {
                return super.set_quantity(...arguments);
            }
            return; // ❌ block increase/edit
        }

        return super.set_quantity(...arguments);
    },
});