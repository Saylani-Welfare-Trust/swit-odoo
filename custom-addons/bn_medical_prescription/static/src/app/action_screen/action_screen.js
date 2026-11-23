/** @odoo-module */

import { ActionScreen } from "@bn_pos_custom_action/app/action_screen/action_screen";
import { patch } from "@web/core/utils/patch";
import { PrescriptionListPopup } from "@bn_medical_prescription/app/popups/prescription_list_popup";

/** Actions > Prescriptions: the approved prescriptions waiting for their bill */
patch(ActionScreen.prototype, {
    get isMedicalCounter() {
        return this.pos.isMedicalCounter;
    },

    async clickPrescriptions() {
        // the Actions popup closes: the prescription list takes its place
        this.cancel();
        const { confirmed, payload } = await this.popup.add(PrescriptionListPopup, {});
        if (confirmed && payload) {
            await this.pos.loadMedicalPrescription(payload);
        }
    },
});
