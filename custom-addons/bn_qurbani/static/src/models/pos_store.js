/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { QurbaniSchedule } from "../app/qurbani_schedule/qurbani_schedule";

patch(PosStore.prototype, {
    async addProductToCurrentOrder(product, options = {}) {

        if (Number.isInteger(product)) {
            product = this.db.get_product_by_id(product);
        }

        const nameHasNo = product.display_name?.toLowerCase().includes("no");

        const isQurbani =
            product.is_livestock &&
            product.detailed_type === "product" &&
            product.categ?.name?.toLowerCase().includes("qurbani");

        let payload = null;

        if (isQurbani) {
            const res = await this.popup.add(QurbaniSchedule, {
                // hissa_no: nameHasNo,
                hissa_no: false,
                product: product,
            });

            if (!res?.confirmed) {
                return false;
            }

            payload = res.payload;
        }

        await super.addProductToCurrentOrder(product, options);

        const order = this.get_order();
        const line = order.get_selected_orderline?.() || order.get_orderlines().slice(-1)[0];

        if (isQurbani && line) {
            line.qurbani_schedule = payload;
            line.customerNote = payload.name || "";
        }
    }
});