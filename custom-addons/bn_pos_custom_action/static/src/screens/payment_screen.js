/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    _getCounterKey(config_id) {
        return `counter_${config_id}`;
    },

    _getCounter() {
        const config_id = this.pos.config.id;
        const key = this._getCounterKey(config_id);

        const currentYear = new Date().getFullYear();

        let counterData = JSON.parse(
            localStorage.getItem(key) || "null"
        );

        // First POS opening
        if (!counterData) {
            counterData = {
                year: currentYear,
                counter: this.pos.config.sequence || 1,
            };

            localStorage.setItem(
                key,
                JSON.stringify(counterData)
            );
        }

        // New year reset
        if (counterData.year !== currentYear) {
            counterData = {
                year: currentYear,
                counter: this.pos.config.sequence || 1,
            };

            localStorage.setItem(
                key,
                JSON.stringify(counterData)
            );
        }

        return counterData;
    },

    _generateReceiptNumber(order) {
        const config_id = this.pos.config.id;

        const key = this._getCounterKey(config_id);

        let counterData = this._getCounter();

        order.set_pos_order_seq(counterData.counter);

        /*
            Increment for next order
        */
        counterData.counter += 1;

        localStorage.setItem(
            key,
            JSON.stringify(counterData)
        );
    },

    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        // One receipt number per order: a retried validation keeps it
        if (!currentOrder.get_pos_order_seq()) {
            this._generateReceiptNumber(currentOrder);
        }
        // Program modules handle their own order data in their own patches
        // (bn_welfare, bn_microfinance, bn_medical_equipment ...); advance
        // donation receipts are created by the server when the order is saved.
        return super.validateOrder(...arguments);
    },
});
