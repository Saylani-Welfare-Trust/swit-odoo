/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkProduct() {
        const orderlines = this.pos.get_order().get_orderlines();

        if (orderlines) {
            if (orderlines.length >= 1) {
                return true;
            }

        } else {
            return false;
        }
    },
    
    async clickRecordQurbani() {
        const order = this.pos.get_order();

        const donor = order.partner ? order.partner : null;

        if (!donor && this.checkProduct) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a donor first..."
            });
        }

        this.popup.add(ReceivingPopup, {
            title: "Qurbani Booking",
            placeholder: "QO/XX/XXXXX",
            action_type: "qb"
        });
    }
});