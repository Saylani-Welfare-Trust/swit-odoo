/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentPopup } from "../../app/payment_popup/payment_popup";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        if (paymentMethod.show_popup) {
            await this.popup.add(PaymentPopup, {
                title: paymentMethod.name,
                label: paymentMethod.name,
                is_bank: paymentMethod.is_bank,
                action_type: paymentMethod.name.toLowerCase()
            });
        }

        if (this.pos.addedOtherInfo && paymentMethod.show_popup) {
            const res = super.addNewPaymentLine(...arguments);
        } else if (!paymentMethod.show_popup) {
            const res = super.addNewPaymentLine(...arguments);
        }
    },
})