/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";


patch(Order.prototype, {
    async pay() {
        var pos_order = this.export_for_printing();

        console.log('Bang Bang');
        console.log(pos_order);

        if(!pos_order.partner) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: _t("Please Select Customer."),
            });
            return false;
        }
        return super.pay(...arguments);
    }
});

