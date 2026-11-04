/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

// Medical equipment security deposits, payments and refunds at the POS.
// The request and its security deposit are updated on the server once the
// order is saved (pos.order._apply_medical_equipment_payment).
patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;
        const medicalData = currentOrder?.extra_data?.medical_equipment;

        if (medicalData) {
            if (
                medicalData.equipment_id &&
                medicalData.equipment_state === "sd_received" &&
                currentOrder.get_orderlines().some((line) => line.get_quantity() < 0)
            ) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Invalid Quantity"),
                    body: _t("You cannot process an order with negative quantities."),
                });
                return;
            }
            const requestNo = medicalData.record_number || medicalData.medical_equipment_request_no;
            if (requestNo) {
                currentOrder.set_source_document(requestNo);
            }
        }

        return super.validateOrder(...arguments);
    },
});
