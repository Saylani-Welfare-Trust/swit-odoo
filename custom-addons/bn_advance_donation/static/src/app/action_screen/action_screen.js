/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { _t } from "@web/core/l10n/translation";

patch(ActionScreen.prototype, {
    get checkAdvanceDonationAccess() {
        // Only allow users in the advance_donation_pos_action_group
        return this.pos._advanceDonation;
    },


    async clickRecordAdvanceDonation() {
        this.popup.add(ReceivingPopup, {
            title: _t("Advance Donation Payment"),
            placeholder: "AD/xxxxxxx",
            action_type: "ad",
        });
    },
});
