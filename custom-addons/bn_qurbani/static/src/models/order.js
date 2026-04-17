/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    async pay() {
        const lines = this.get_orderlines();

        // Allow only letters, numbers and spaces
        const validRegex = /^[a-zA-Z]+$/;

        for (const line of lines) {
            const product = line.product;

            const isQurbaniLivestock =
                product.is_livestock &&
                product.detailed_type === "product" &&
                product.categ?.name?.toLowerCase().includes("qurbani");

            if (!isQurbaniLivestock) continue;

            const note = line.customerNote?.trim();

            // ❌ Empty or too short
            if (!note || note.length < 3) {
                this.env.services.notification.add(
                    `Customer note must be at least 3 characters for product: ${product.display_name}`,
                    { type: "warning" }
                );
                return;
            }

            // ❌ Contains special characters
            if (!validRegex.test(note)) {
                this.env.services.notification.add(
                    `Customer note cannot contain special characters for product: ${product.display_name}`,
                    { type: "warning" }
                );
                return;
            }
        }

        return await super.pay(...arguments);
    }
});