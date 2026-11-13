/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    async pay() {
        if (this.pos.config.is_medical_pos && !this.get_partner()) {
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Patient Required"),
                body: _t("Please select the patient first."),
            });
        }
        return super.pay(...arguments);
    },
});
