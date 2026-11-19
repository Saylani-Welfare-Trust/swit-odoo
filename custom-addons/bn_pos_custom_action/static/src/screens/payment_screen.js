/** @odoo-module **/

// The receipt number (pos_order_seq, the last part of the DN #) is no longer
// counted in the browser (each browser had its own counter, so two screens of a
// counter printed the same numbers): the server gives it when the order is
// saved, one sequence per Branch and counter that restarts every year
// (pos.order._assign_pos_order_seq), and sends it back for the receipt
// (store/pos_store.js).

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        // Program modules handle their own order data in their own patches
        // (bn_welfare, bn_microfinance, bn_medical_equipment ...); advance
        // donation receipts are created by the server when the order is saved.
        return super.validateOrder(...arguments);
    },
});
