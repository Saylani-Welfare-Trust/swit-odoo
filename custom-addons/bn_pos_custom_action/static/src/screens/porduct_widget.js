/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        console.log('PATCH FIRED');
        const products = super.productsToDisplay;
        const order = this.pos.get_order();
        if (!order) {
            console.log('NO ORDER');
            return products;
        }

        const returnedProductIds = new Set(
            order
                .get_orderlines()
                .filter((line) => line.refunded_orderline_id)
                .map((line) => line.product.id)
        );

        console.log('Returned IDs:', [...returnedProductIds]);

        if (!returnedProductIds.size) {
            return products;
        }

        return products.filter((product) => !returnedProductIds.has(product.id));
    },
});