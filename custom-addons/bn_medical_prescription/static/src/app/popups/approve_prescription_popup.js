/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useService } from "@web/core/utils/hooks";
import { onMounted, useRef, useState } from "@odoo/owl";

/**
 * First phase of the Medical & Health counter: choose the doctor of the selected products
 * before the payment of the till. Resolves with { doctor_id, doctor_name, note }.
 *
 * @props order
 * @props doctors - [{ id, name }] the doctors of the selected products
 */
export class ApprovePrescriptionPopup extends AbstractAwaitablePopup {
    static template = "bn_medical_prescription.ApprovePrescriptionPopup";
    // approving takes a click on the button, Enter in a field doesn't
    static defaultProps = { confirmKey: false, cancelKey: "Escape" };

    setup() {
        super.setup();
        // Own the numpad buffer while open, so keystrokes can't edit the order line underneath
        useService("number_buffer").use();
        this.doctorInput = useRef("doctorInput");
        const { order, doctors } = this.props;
        const preselected = doctors.find((doctor) => doctor.id === order.medical_doctor_id) ||
            (doctors.length === 1 ? doctors[0] : null);
        this.state = useState({
            doctor_id: preselected ? String(preselected.id) : "",
            note: order.medical_note || "",
        });
        onMounted(() => this.doctorInput.el?.focus());
    }

    isSelected(doctor) {
        return String(doctor.id) === this.state.doctor_id;
    }

    onDoctorChange(ev) {
        this.state.doctor_id = ev.target.value;
    }

    get partner() {
        return this.props.order.get_partner();
    }

    get lines() {
        return this.props.order.get_orderlines().map((line) => ({
            id: line.cid || line.id,
            name: line.get_full_product_name(),
            qty: line.get_quantity_str(),
            unit: line.get_unit()?.name || "",
            amount: this.env.utils.formatCurrency(line.get_price_with_tax()),
        }));
    }

    get total() {
        return this.env.utils.formatCurrency(this.props.order.get_total_with_tax());
    }

    async getPayload() {
        const doctor = this.props.doctors.find((doctor) => String(doctor.id) === this.state.doctor_id);
        return { doctor_id: doctor.id, doctor_name: doctor.name, note: this.state.note.trim() };
    }
}
