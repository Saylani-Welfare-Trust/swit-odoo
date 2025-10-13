/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {
    // Set the transaction ID
    set_transaction_id(transaction_id) {
        this.transaction_id = transaction_id;
    },

    // Get the transaction ID
    get_transaction_id() {
        return this.transaction_id;
    },

    // Set the QR code
    set_qr_code(qr_code) {
        this.qr_code = qr_code;
    },

    // Get the QR code
    get_qr_code() {
        return this.qr_code;
    },

    // Override export_as_JSON to include transaction_id and qr_code
    export_as_JSON() {
        const json = super.export_as_JSON();
        // Include the new fields in the exported JSON
        json.transaction_id = this.get_transaction_id() || null;
        json.qr_code = this.get_qr_code() || null;
        return json;
    },

    // Override export_for_printing to include transaction_id and qr_code
    export_for_printing() {
        const order = super.export_for_printing();
        const new_val = {
            transaction_id: this.get_transaction_id() || false,
            qr_code: this.get_qr_code() || false,
        };

        // // Add cover_image if available in the POS environment
        // let cover_image = false;
        // if (this.env && this.env.pos && this.env.pos.cover_image) {
        //     cover_image = this.env.pos.cover_image;
        // }
        // new_val.cover_image = cover_image || false;

        // Merge the new values with the existing order details
        Object.assign(order, new_val);
        return order;
    },
});
