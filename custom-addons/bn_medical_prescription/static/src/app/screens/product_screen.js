/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// The quantities and prices of a prescription were approved at the prescription desk: the billing counter can't change them
patch(ProductScreen.prototype, {
    get selectedPrescriptionLine() {
        const line = this.pos.get_order()?.get_selected_orderline();
        return line?.medical_prescription_line_id ? line : null;
    },

    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!this.selectedPrescriptionLine) {
            return buttons;
        }
        return buttons.map((button) => ({ ...button, disabled: true }));
    },

    async updateSelectedOrderline() {
        if (this.selectedPrescriptionLine) {
            this.numberBuffer.reset();
            this.notification.add(
                _t("Approved prescription lines can't be changed: the prescription desk has to change the prescription."),
                4000
            );
            return;
        }
        return super.updateSelectedOrderline(...arguments);
    },
});
