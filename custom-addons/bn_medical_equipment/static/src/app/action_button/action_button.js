/** @odoo-module */

import { ActionButton } from "@bn_pos_custom_action/app/action_button/action_button";
import { patch } from "@web/core/utils/patch";


patch(ActionButton.prototype, {
    async setup() {
        await super.setup(...arguments);
        const user = this.env.services.user;
        this.pos._medicalEquipment = await user.hasGroup('bn_medical_equipment.medical_equipment_pos_action_group');
        this.pos._medicalEquipmentSettleOrder = await user.hasGroup('bn_medical_equipment.medical_equipment_pos_settle_action_group');
        this.pos._medicalEquipmentSecurityDeposit = await user.hasGroup('bn_medical_equipment.medical_equipment_pos_security_deposit_action_group');
    },
});
