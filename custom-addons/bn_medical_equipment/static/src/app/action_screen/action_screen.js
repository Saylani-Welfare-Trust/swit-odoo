/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { ReceivingPopup } from "@bn_pos_custom_action/app/receiving_popup/receiving_popup";
import { patch } from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";


patch(ActionScreen.prototype, {
    get checkMedicalEquipment() {
        const orderlines = this.pos.get_order().get_orderlines();

        if (orderlines) {
            if (orderlines.length === 1) {
                const product = orderlines[0].get_product();
                return product && product.is_medical_equipment === true;
            }
            
            // Multiple lines
            return orderlines.some(line => {
                const product = line.get_product();
                return product && product.is_medical_equipment === true;
            });
        } else {
            return false;
        }
    },
    
    async clickRecordME() {
        this.popup.add(ReceivingPopup, {
            title: "Medical Equipment",
            placeholder: "ME/XX/XXXXX",
            action_type: "me"
        });
    }
});