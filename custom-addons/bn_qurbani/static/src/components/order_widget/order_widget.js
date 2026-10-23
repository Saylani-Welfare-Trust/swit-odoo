/** @odoo-module */

import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";

patch(OrderWidget.prototype, {
    getTotalQty() {
        const order = this.env.services.pos.get_order();

        if (!order) return 0;

        return order.get_orderlines().reduce(
            (sum, line) => sum + line.get_quantity(),
            0
        );
    },
});