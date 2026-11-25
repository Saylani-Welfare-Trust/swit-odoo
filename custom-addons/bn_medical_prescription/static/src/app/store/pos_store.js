/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ApprovePrescriptionPopup } from "@bn_medical_prescription/app/popups/approve_prescription_popup";
import { PrescriptionListPopup } from "@bn_medical_prescription/app/popups/prescription_list_popup";
import { patch } from "@web/core/utils/patch";
import { sprintf } from "@web/core/utils/strings";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /** A Medical & Health POS: one counter for the paid till and the bill of the approved prescription */
    get isMedicalCounter() {
        return Boolean(this.config.is_medical_pos);
    },

    notifyMedical(message, type = "info") {
        this.env.services.notification.add(message, { type });
    },

    /** Selecting the patient loads their approved prescription */
    async selectPartner() {
        const order = this.get_order();
        const previousId = order?.get_partner()?.id || false;
        const result = await super.selectPartner(...arguments);
        if (!this.isMedicalCounter || !order || order !== this.get_order()) {
            return result;
        }
        const partner = order.get_partner();
        if ((partner?.id || false) !== previousId) {
            if (order.medical_prescription_id) {
                // the loaded prescription was for the previous patient
                this.removeMedicalPrescription(order);
            }
            if (partner) {
                await this.offerMedicalPrescriptions(partner);
            }
        }
        return result;
    },

    async fetchMedicalPrescriptions({ partnerId = false, term = "" } = {}) {
        return await this.orm.call("pos.session", "pos_get_medical_prescriptions", [
            [this.pos_session.id],
            partnerId,
            term,
        ]);
    },

    async offerMedicalPrescriptions(partner) {
        const prescriptions = await this.fetchMedicalPrescriptions({ partnerId: partner.id });
        if (!prescriptions.length) {
            return;
        }
        if (this.get_order()?.get_orderlines().length) {
            // the order is already a new till: don't mix the prescription into it
            this.notifyMedical(
                sprintf(_t("%s has an approved prescription: open Actions > Prescriptions to bill it."), partner.name),
                "warning"
            );
            return;
        }
        let prescription = prescriptions[0];
        if (prescriptions.length > 1) {
            const { confirmed, payload } = await this.popup.add(PrescriptionListPopup, {
                title: sprintf(_t("Prescriptions of %s"), partner.name),
                partner,
                prescriptions,
            });
            if (!confirmed || !payload) {
                return;
            }
            prescription = payload;
        }
        await this.loadMedicalPrescription(prescription);
    },

    /** Put the approved products of the prescription on the order, locked */
    async loadMedicalPrescription(prescription, order = this.get_order()) {
        if (!order) {
            return false;
        }
        if (order.medical_prescription_id === prescription.id) {
            this.notifyMedical(sprintf(_t("%s is already on this order."), prescription.name));
            return true;
        }

        // products outside the categories of this POS aren't loaded yet
        const missingIds = [
            ...new Set(prescription.lines.map((line) => line.product_id)),
        ].filter((id) => !this.db.get_product_by_id(id));
        if (missingIds.length) {
            await this._addProducts(missingIds, false);
        }
        const unavailable = prescription.lines.filter((line) => !this.db.get_product_by_id(line.product_id));
        if (unavailable.length) {
            await this.popup.add(ErrorPopup, {
                title: _t("Products not available"),
                body: sprintf(
                    _t("These products of %s can't be sold in this POS: %s"),
                    prescription.name,
                    unavailable.map((line) => line.product_name).join(", ")
                ),
            });
            return false;
        }

        if (order.medical_prescription_id) {
            this.removeMedicalPrescription(order);
        }
        if (order.get_orderlines().length) {
            // products of a till in progress: it stays as its own order
            order = this.add_new_order();
        }
        if (prescription.partner && order.get_partner()?.id !== prescription.partner.id) {
            this.addPartners([prescription.partner]);
            order.set_partner(this.db.get_partner_by_id(prescription.partner.id) || prescription.partner);
        }
        for (const line of prescription.lines) {
            await order.add_product(this.db.get_product_by_id(line.product_id), {
                quantity: line.qty,
                price: line.price_unit,
                discount: line.discount,
                merge: false,
                extras: { price_type: "manual", medical_prescription_line_id: line.id },
            });
            if (line.note) {
                // the added line is selected; through the order it is the reactive one
                order.get_selected_orderline()?.set_customer_note(line.note);
            }
        }
        order.medical_prescription_id = prescription.id;
        order.medical_prescription_name = prescription.name;
        order.medical_doctor_id = false;
        order.medical_doctor_name = prescription.doctor_name || false;
        this.notifyMedical(
            sprintf(_t("Prescription %s loaded: %s product(s)."), prescription.name, prescription.lines.length),
            "success"
        );
        return true;
    },

    removeMedicalPrescription(order = this.get_order()) {
        for (const line of [...order.get_orderlines()]) {
            if (line.medical_prescription_line_id) {
                order.removeOrderline(line);
            }
        }
        order.medical_prescription_id = false;
        order.medical_prescription_name = false;
        order.medical_doctor_name = false;
    },

    /**
     * First phase: Approve asks for the doctor of the selected products, then the order is paid as usual.
     * The paid till makes the draft prescription on the server.
     * @returns {Promise<boolean>} whether the payment can go on
     */
    async selectMedicalDoctor(order = this.get_order()) {
        const partner = order.get_partner();
        const lines = order.get_orderlines();
        let error = "";
        if (!partner) {
            error = _t("Please select the patient first.");
        } else if (lines.some((line) => line.get_quantity() <= 0)) {
            error = _t("Quantities must be positive.");
        }
        if (error) {
            await this.popup.add(ErrorPopup, { title: _t("Can't approve"), body: error });
            return false;
        }

        const products = [...new Set(lines.map((line) => line.get_product()))];
        const doctors = await this.orm.call("pos.session", "pos_get_medical_doctors", [
            [this.pos_session.id],
            products.map((product) => product.id),
        ]);
        if (!doctors.length) {
            await this.popup.add(ErrorPopup, {
                title: _t("No doctor for these products"),
                body: sprintf(
                    _t("No doctor is listed on all of: %s. Add them in Master Setup > Doctors, or bill them separately."),
                    products.map((product) => product.display_name).join(", ")
                ),
            });
            return false;
        }

        const { confirmed, payload } = await this.popup.add(ApprovePrescriptionPopup, { order, doctors });
        if (!confirmed) {
            return false;
        }
        order.medical_doctor_id = payload.doctor_id;
        order.medical_doctor_name = payload.doctor_name;
        order.medical_note = payload.note;
        return true;
    },
});
