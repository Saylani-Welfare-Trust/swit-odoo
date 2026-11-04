/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;
        
        // Only process medical equipment if order has extra_data with medical_equipment
        if (currentOrder && currentOrder.extra_data && currentOrder.extra_data.donation_box) {
            const donationBoxData = currentOrder.extra_data.donation_box;

            if (donationBoxData) {
                // 🔹 First call your custom method
                const data = await this.orm.call('key.issuance', "set_donation_amount", [donationBoxData]);

                if (data.status === 'error') {
                    this.popup.add(ErrorPopup, {
                        title: _t("Error"),
                        body: data.body,
                    });
                    return;
                }

                if (data.status === 'success') {
                    this.env.services.notification.add(_t("Amount Recorded Successfully"), { type: "success" });
                }
            }
        }

        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
    }
})