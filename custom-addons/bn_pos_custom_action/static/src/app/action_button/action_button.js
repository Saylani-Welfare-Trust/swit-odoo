/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ActionScreen } from "../action_screen/action_screen";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class ActionButton extends Component {
    static template = "bn_pos_custom_action.ActionButton";

    async setup() {
        this.pos = usePos();
        this.popup = useService("popup");

        this.pos._welfare = await this.env.services.user.hasGroup('bn_welfare.welfare_pos_action_group')
        this.pos._microFinance = await this.env.services.user.hasGroup('bn_microfinance.microfinance_pos_action_group')
        this.pos._directDeposit = await this.env.services.user.hasGroup('bn_direct_deposit.direct_deposit_pos_action_group')
        this.pos._medicalEquipment = await this.env.services.user.hasGroup('bn_medical_equipment.medical_equipment_pos_action_group')
        this.pos._medicalEquipmentSettleOrder = await this.env.services.user.hasGroup('bn_medical_equipment.medical_equipment_pos_settle_action_group')
        this.pos._medicalEquipmentSecurityDeposit = await this.env.services.user.hasGroup('bn_medical_equipment.medical_equipment_pos_security_deposit_action_group')
        this.pos._advanceDonation = await this.env.services.user.hasGroup('bn_advance_donation.advance_donation_pos_action_group')
    }

    async onClick() {
        this.popup.add(ActionScreen);
    }
}

ProductScreen.addControlButton({
    component: ActionButton,
});
