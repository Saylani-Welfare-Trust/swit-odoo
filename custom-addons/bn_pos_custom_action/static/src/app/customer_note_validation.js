/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;

        if (currentOrder) {
            const donationInKindLines = currentOrder
                .get_orderlines()
                .filter(
                    (line) =>
                        line.product &&
                        line.product.is_donation_in_kind === true
                );

            // If there is at least one Donation In Kind product,
            // at least one of them must have a customer note.
            if (donationInKindLines.length > 0) {
                const missingNoteLine = donationInKindLines.find(
                    (line) =>
                        !line.customerNote ||
                        !line.customerNote.trim()
                );


                if (missingNoteLine) {
                    await this.popup.add(ErrorPopup, {
                        title: _t("Customer Note Required"),
                        body: _t(
                            "Please enter a customer note for every Donation In Kind product before making the payment."
                        ),
                    });

                    return;
                }
            }
        }

        return super.validateOrder(isForceValidate);
    },
});