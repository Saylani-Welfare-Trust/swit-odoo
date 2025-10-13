/** @odoo-module **/

import { PosDB } from "@point_of_sale/app/store/db";
import { patch } from "@web/core/utils/patch";

patch(PosDB.prototype, {
    get_orders() {
        const order = this.load("orders", []);
        console.log(this.load)
        return order;
    },
    add_registered_order(order) {
        var order_id = order.id;
        var orders = this.load("registered_orders", []);

        for (var i = 0, len = orders.length; i < len; i++) {
            if (orders[i].id === order_id) {
                orders[i].data = order;
                this.save("orders", orders);
                return order_id;
            }
        }
    },
    // get_product_by_category(category_id) {
    //     var product_ids = [...new Set(Object.values(this.product_by_category_id).flat())]
    //     var list = [];
    //     if (product_ids) {
    //         for (var i = 0, len = Math.min(product_ids.length, this.limit); i < len; i++) {
    //             const product = this.product_by_id[product_ids[i]];
    //             if (!this.shouldAddProduct(product, list)) {
    //                 continue;
    //             }
    //             list.push(product);
    //         }
    //     }
    //     return list;
    // }
});
