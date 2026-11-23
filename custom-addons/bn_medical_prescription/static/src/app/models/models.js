/** @odoo-module */

import { Order, Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    async pay() {
        // an order without a prescription is the till of the first phase: it needs its doctor
        if (
            this.pos.isMedicalCounter &&
            this.canPay() &&
            !this.medical_prescription_id &&
            !this.getHasRefundLines() &&
            !(await this.pos.selectMedicalDoctor(this))
        ) {
            return;
        }
        return super.pay(...arguments);
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.medical_prescription_id = json.medical_prescription_id || false;
        this.medical_prescription_name = json.medical_prescription_name || false;
        this.medical_doctor_id = json.medical_doctor_id || false;
        this.medical_doctor_name = json.medical_doctor_name || false;
        this.medical_note = json.medical_note || false;
        this.medical_till_name = json.medical_till_name || false;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.medical_prescription_id = this.medical_prescription_id || false;
        json.medical_prescription_name = this.medical_prescription_name || false;
        json.medical_doctor_id = this.medical_doctor_id || false;
        json.medical_doctor_name = this.medical_doctor_name || false;
        json.medical_note = this.medical_note || false;
        json.medical_till_name = this.medical_till_name || false;
        return json;
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.medical_prescription_name = this.medical_prescription_name || false;
        result.medical_doctor_name = this.medical_doctor_name || false;
        result.medical_receipt_number = this.medical_prescription_name || this.medical_till_name || false;
        result.medical_receipt_title = this.medical_prescription_name
            ? _t("Medical Bill")
            : this.medical_doctor_id
            ? _t("Medical Till")
            : false;
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
