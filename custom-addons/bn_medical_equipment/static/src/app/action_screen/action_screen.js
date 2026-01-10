/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkMedicalEquipmentAccess(){
        // console.log(this);

        return this.pos._medicalEquipment || false;
    },

    async clickRecordME() {
        this.popup.add(ReceivingPopup, {
            title: "Medical Equipment",
            placeholder: "ME/XX/XXXXX",
            action_type: "me"
        });
    }
});