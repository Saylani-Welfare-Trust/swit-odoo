/** @odoo-module */

import { Order, Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    async pay() {
        if (this.pos.isPrescriptionDesk) {
            // the desk approves the products, the patient pays at the billing counter
            return this.pos.approveMedicalPrescription(this);
        }
        return super.pay(...arguments);
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.medical_prescription_id = json.medical_prescription_id || false;
        this.medical_prescription_name = json.medical_prescription_name || false;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.medical_prescription_id = this.medical_prescription_id || false;
        json.medical_prescription_name = this.medical_prescription_name || false;
        return json;
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.medical_prescription_name = this.medical_prescription_name || false;
        if (result.partner && this.partner) {
            result.partner = { ...result.partner, registration_id: this.partner.primary_registration_id || "" };
        }
        return result;
    },
});

patch(Orderline.prototype, {
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.medical_prescription_line_id = json.medical_prescription_line_id || false;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.medical_prescription_line_id = this.medical_prescription_line_id || false;
        return json;
    },

    /** A prescribed line keeps its approved quantity: the same product is added on its own line */
    can_be_merged_with(orderline) {
        if (this.medical_prescription_line_id || orderline.medical_prescription_line_id) {
            return false;
        }
        return super.can_be_merged_with(...arguments);
    },

    getDisplayData() {
        return {
            ...super.getDisplayData(...arguments),
            medicalPrescription: Boolean(this.medical_prescription_line_id),
        };
    },
});
