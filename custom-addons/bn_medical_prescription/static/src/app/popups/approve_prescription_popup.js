/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useService } from "@web/core/utils/hooks";
import { onMounted, useRef, useState } from "@odoo/owl";

/**
 * Prescription desk: review the products of the order before approving them for the patient.
 * Resolves with { doctor_name, note }.
 *
 * @props order
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
        this.state = useState({ doctor_name: "", note: "" });
        onMounted(() => this.doctorInput.el?.focus());
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
            note: line.get_customer_note() || "",
        }));
    }

    get total() {
        return this.env.utils.formatCurrency(this.props.order.get_total_with_tax());
    }

    async getPayload() {
        return { doctor_name: this.state.doctor_name.trim(), note: this.state.note.trim() };
    }
}
