/** @odoo-module */

import { Component } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { PrescriptionListPopup } from "@bn_medical_prescription/app/popups/prescription_list_popup";
import { useService } from "@web/core/utils/hooks";

/** Approved prescriptions waiting for their bill: billed from here at the billing counter, cancelled at the desk */
export class PrescriptionButton extends Component {
    static template = "bn_medical_prescription.PrescriptionButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async onClick() {
        const { confirmed, payload } = await this.popup.add(PrescriptionListPopup, {});
        if (confirmed && payload) {
            await this.pos.loadMedicalPrescription(payload);
        }
    }
}

ProductScreen.addControlButton({
    component: PrescriptionButton,
    condition() {
        return Boolean(this.pos.medicalCounter);
    },
});
