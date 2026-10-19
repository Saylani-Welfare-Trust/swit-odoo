/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    /**
     * Override export_as_JSON to include custom fields
     */
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);

        json.source_document = this.source_document || false;
        json.receive_voucher = this.receive_voucher || false;
        json.pos_order_seq = this.pos_order_seq || false;
        json.qurbani = this.qurbani || false;
        json.extra_data = this.extra_data || false;
        
        return json;
    },

    /**
     * 🟢 NEW: Override export_for_printing so the receipt gets the data
     */
    export_for_printing() {
        const json = super.export_for_printing(...arguments);

        // Fetch branch details from the POS Config (Shop)
        if (this.pos && this.pos.config) {
            json.branch_name = this.pos.config.branch_name || false;
            json.branch_code = this.pos.config.branch_code || false;
        }

        // Also pass the existing custom fields for the receipt
        json.source_document = this.source_document || false;
        json.receive_voucher = this.receive_voucher || false;
        json.pos_order_seq = this.pos_order_seq || false;
        json.qurbani = this.qurbani || false;
        json.extra_data = this.extra_data || false;

        return json;
    },

    /**
     * Setter for source_document
     */
    set_source_document(source_document) {
        this.source_document = source_document;
    },

    /**
     * Getter for source_document
     */
    get_source_document() {
        return this.source_document;
    },

    /**
     * Setter for qurbani
     */
    set_qurbani(qurbani) {
        this.qurbani = qurbani;
    },

    /**
     * Getter for qurbani
     */
    get_qurbani() {
        return this.qurbani;
    },

    /**
     * Setter for receive_voucher
     */
    set_receive_voucher(receive_voucher) {
        this.receive_voucher = receive_voucher;
    },

    /**
     * Getter for receive_voucher
     */
    get_receive_voucher() {
        return this.receive_voucher;
    },

    /**
     * Setter for pos_cheque_order_id
     */
    set_pos_cheque_order_id(pos_cheque_order_id) {
        this.pos_cheque_order_id = pos_cheque_order_id;
    },

    /**
     * Getter for pos_cheque_order_id
     */
    get_pos_cheque_order_id() {
        return this.pos_cheque_order_id;
    },

    /**
     * Setter for pos_order_seq
     */
    set_pos_order_seq(pos_order_seq) {
        this.pos_order_seq = pos_order_seq;
    },

    /**
     * Getter for pos_order_seq
     */
    get_pos_order_seq() {
        return this.pos_order_seq;
    },
});