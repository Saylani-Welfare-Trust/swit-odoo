/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        // Check the donation box is still open; the collection is closed on
        // the server once the order is saved (pos.order._process_order).
        const donationBoxData = this.currentOrder?.extra_data?.donation_box;
        if (donationBoxData) {
            const data = await this.orm.call("key.issuance", "set_donation_amount", [
                { ...donationBoxData, check_validation: true },
            ]);
            if (data.status === "error") {
                this.popup.add(ErrorPopup, {
                    title: _t("Error"),
                    body: data.body,
                });
                return;
            }
        }
        return super.validateOrder(...arguments);
    },
});
