/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { QurbaniSchedule } from "../app/qurbani_schedule/qurbani_schedule";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.enable_qurbani = loadedData["enable_qurbani"] || false;
    },

    // Qurbani products only get the Qurbani flow when "Enable Qurbani" is ticked in POS settings
    isQurbaniProduct(product) {
        return (
            this.enable_qurbani &&
            product.is_livestock &&
            product.detailed_type === "product" &&
            product.categ?.name?.toLowerCase().includes("qurbani")
        );
    },

    async addProductToCurrentOrder(product, options = {}) {

        if (Number.isInteger(product)) {
            product = this.db.get_product_by_id(product);
        }

        const isQurbani = this.isQurbaniProduct(product);

        let payload = null;

        if (isQurbani) {
            const res = await this.popup.add(QurbaniSchedule, {
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