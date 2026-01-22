/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ProvisionalPopup } from "@bn_pos_custom_action/app/provisional_popup/provisional_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkDirectDepositAccess(){
        // console.log(this);

        return this.pos._directDeposit || false;
    },

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
    
    async clickRecordDD() {
        const order = this.pos.get_order();
        const donor = order.partner ? order.partner : null;
        const orderLines = order.get_orderlines();

        if (!donor) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please select a donor first..."
            });
        }

        console.log(this);

        if (!orderLines || orderLines.length === 0) {
            return this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Please add at least one product to the order..."
            });
        }

        const amount = order.get_total_with_tax();

        this.popup.add(ProvisionalPopup, {
            donor_id: donor.id,
            donor_name: donor.name,
            donor_address: donor.address,
            orderLines: orderLines,
            amount: amount,
            action_type: "dd"
        });
    }
});