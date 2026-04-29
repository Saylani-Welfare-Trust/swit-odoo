/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    hasQurbani(order) {
        return order.get_orderlines().some(line => {
            const product = line.product;
            return (
                product.is_livestock &&
                product.detailed_type === "product" &&
                product.categ?.name?.toLowerCase().includes("qurbani")
            );
        });
    },

    set_quantity(quantity, keep_price) {
        console.log(quantity);
        console.log(this);

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