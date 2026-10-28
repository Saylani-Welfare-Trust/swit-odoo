/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentPopup } from "../../app/payment_popup/payment_popup";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        if (paymentMethod.show_popup) {
            // only a confirmed popup (cheque / QR details filled) adds the line
            this.pos.addedOtherInfo = false;
            await this.popup.add(PaymentPopup, {
                title: paymentMethod.name,
                label: paymentMethod.name,
                is_bank: paymentMethod.is_bank,
                action_type: paymentMethod.name.toLowerCase()
            });
            if (!this.pos.addedOtherInfo) {
                return false;
            }
        }

        if (paymentMethod.is_donation_in_kind) {
            this.pos.get_order().donation_in_kind = true;
        }

        return super.addNewPaymentLine(...arguments);
    },
});
